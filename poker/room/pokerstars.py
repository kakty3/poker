# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import re
import logging
from itertools import ifilter
from decimal import Decimal
from datetime import datetime
from collections import namedtuple
from lxml import etree
import pytz
from pathlib import Path
from zope.interface import implementer
from .. import handhistory as hh
from ..card import Card
from ..hand import Combo
from ..constants import Limit, Game, GameType, Currency, Action, MoneyType


__all__ = ['PokerStarsHandHistory', 'Notes']


logger = logging.getLogger(__name__)
logger.setLevel(level=logging.ERROR)


@implementer(hh.IStreet)
class _Street(hh._BaseStreet):
    def _parse_cards(self, boardline):
        self.cards = (Card(boardline[1:3]), Card(boardline[4:6]), Card(boardline[7:9]))

    def _parse_actions(self, actionlines):
        ap = ActionParser()
        actions = list()
        for action_str in actionlines:
            try:
                action = ap.parse(action_str)
                actions.append(action)
            except UnknownActionError as e:
                logger.warning(e.message)

        self.actions = tuple(actions) if actions else None


class ActionParser(object):
    _player_action_re = re.compile(r'^(?P<name>.+):\s+(?P<action>.+?\b)\s*(?:[^\d]*?(?P<amount>\d+(?:\.\d+)?))?')
    _uncalled_re = re.compile(r'^Uncalled bet \([^\d]*?(?P<amount>\d+(?:\.\d+)?)\) returned to\s+(?P<name>.+)$')
    _collected_re = re.compile(r'^(?P<name>.+?) collected [^\d]*?(?P<amount>\d+(?:\.\d+)?)')
    _join_re = re.compile(r'^(?P<name>.+?) joins the table at seat #(?P<seat>\d+)$')

    def parse(self, action_str):
        parse_methods = (
            ('Uncalled bet', self._parse_uncalled),
            (' collected ', self._parse_collected),
            (' doesn\'t show hand', self._parse_muck),
            ('mucks hand', self._parse_muck),
            ('joins the table', self._parse_join_table),
            ('leaves the table', self._parse_leave_table),
            ('has timed out', self._parse_timed_out),
            ('is connected', self._parse_connected),
            ('is disconnected', self._parse_disconnected),
            ('was removed', self._parse_removed),
            (' shows ', self._parse_show),
            (': ', self._parse_player_action),
        )
        try:
            _, parse_function =\
                ifilter(lambda (substr, _): substr in action_str, parse_methods).next()
            name, action, value = parse_function(action_str.strip())
        except StopIteration:
            raise UnknownActionError(action_str)

        return hh._PlayerAction(name, action, value)

    def _parse_show(self, line):
        name = line[:line.index(':')]
        cards_str = line[line.index('[') + 1:line.index(']')]
        combo = Combo.from_array(cards_str.split())
        return name, Action.SHOW, combo

    def _parse_uncalled(self, line):
        match = self._uncalled_re.match(line)
        name = match.group('name')
        amount = match.group('amount')
        return name, Action.RETURN, Decimal(amount)

    def _parse_removed(self, line):
        i = line.index('was removed')
        name = line[:i].strip()
        return name, Action.REMOVED, None

    def _parse_collected(self, line):
        match = self._collected_re.match(line)
        name = match.group('name')
        amount = match.group('amount')
        # self.pot = Decimal(amount)
        return name, Action.WIN, Decimal(amount)

    def _parse_muck(self, line):
        colon_index = line.find(':')
        name = line[:colon_index]
        return name, Action.MUCK, None

    def _parse_player_action(self, line):
        match = self._player_action_re.match(line)
        name = match.group('name')
        action = Action(match.group('action'))
        try:
            amount = Decimal(match.group('amount'))
        except TypeError:
            amount = None

        return name, action, amount

    def _parse_join_table(self, line):
        match = self._join_re.match(line)
        return match.group('name'), Action.JOIN, match.group('seat')

    def _parse_leave_table(self, line):
        i = line.index('leaves the table')
        name = line[:i].strip()
        return name, Action.LEAVE, None

    def _parse_timed_out(self, line):
        i = line.index('has timed out')
        name = line[:i].strip()
        return name, Action.TIMED_OUT, None

    def _parse_disconnected(self, line):
        i = line.index('is disconnected')
        name = line[:i].strip()
        return name, Action.DISCONNECTED, None

    def _parse_connected(self, line):
        i = line.index('is connected')
        name = line[:i].strip()
        return name, Action.CONNECTED, None


class UnknownActionError(Exception):
    def __init__(self, action_str):
        super(UnknownActionError, self).__init__('Unknown action: %s.' % action_str)


@implementer(hh.IHandHistory)
class PokerStarsHandHistory(hh._SplittableHandHistoryMixin, hh._BaseHandHistory):
    """Parses PokerStars Tournament hands."""

    _DATE_FORMAT = '%Y/%m/%d %H:%M:%S ET'
    _TZ = pytz.timezone('US/Eastern')  # ET
    _split_re = re.compile(r" ?\*\*\* ?\n?|\n")
    _header_re = re.compile(r"""
                        ^PokerStars\s+                                # Poker Room
                        Hand\s+\#(?P<ident>\d+):\s+                   # Hand history id
                        (Tournament\s+\#(?P<tournament_ident>\d+),\s+ # Tournament Number
                         ((?P<freeroll>Freeroll)|(                    # buyin is Freeroll
                          \$?(?P<buyin>\d+(\.\d+)?)                   # or buyin
                          (\+\$?(?P<rake>\d+(\.\d+)?))?               # and rake
                          (\s+(?P<currency>[A-Z]+))?                  # and currency
                         ))\s+
                        )?
                        (?P<game>.+?)\s+                              # game
                        (?P<limit>(?:Pot\s+|No\s+|)Limit)\s+          # limit
                        (-\s+Level\s+(?P<tournament_level>\S+)\s+)?   # Level (optional)
                        \(
                         (((?P<sb>\d+)/(?P<bb>\d+))|(                 # tournament blinds
                          \$(?P<cash_sb>\d+(\.\d+)?)/                 # cash small blind
                          \$(?P<cash_bb>\d+(\.\d+)?)                  # cash big blind
                          (\s+(?P<cash_currency>\S+))?                # cash currency
                         ))
                        \)\s+
                        -\s+.+?\s+                                    # localized date
                        \[(?P<date>.+?)\]                             # ET date
                        """, re.VERBOSE)
    _table_re = re.compile(r"^Table '(.*)' (\d+)-max Seat #(?P<button>\d+) is the button")
    _seat_re = re.compile(r"^Seat (?P<seat>\d+): (?P<name>.+?) \(\$?(?P<stack>\d+(\.\d+)?) in chips\)")  # noqa
    _hero_re = re.compile(r"^Dealt to (?P<hero_name>.+?) \[(?P<cards>.+?)\]")
    _pot_re = re.compile(r"^Total pot [^\d]*?(\d+(?:\.\d+)?) .*\| Rake [^\d]*?(\d+(?:\.\d+)?)")
    _winner_re = re.compile(r"^Seat (?:\d+): (?P<name>.+?)\s?(?:\(.+?\))? collected \([^\d]*?(?P<amount>\d+(?:\.\d+)?)\)")
    _showdown_re = re.compile(r"^Seat (?:\d+): (?P<name>.+?)\s?(?:\(.+?\))? showed \[.+?\] and won")
    _ante_re = re.compile(r".*posts the ante (\d+(?:\.\d+)?)")
    _board_re = re.compile(r"(?<=[\[ ])(..)(?=[\] ])")
    _money_re = re.compile(r"\$\d+\.?\d+")

    def parse_header(self):
        # sections[0] is before HOLE CARDS
        # sections[-1] is before SUMMARY
        self._split_raw()

        match = self._header_re.match(self._splitted[0])

        self.extra = dict()
        self.ident = match.group('ident')

        # We cannot use the knowledege of the game type to pick between the blind
        # and cash blind captures because a cash game play money blind looks exactly
        # like a tournament blind

        self.sb = Decimal(match.group('sb') or match.group('cash_sb'))
        self.bb = Decimal(match.group('bb') or match.group('cash_bb'))

        if match.group('tournament_ident'):
            self.game_type = GameType.TOUR
            self.tournament_ident = match.group('tournament_ident')
            self.tournament_level = match.group('tournament_level')

            currency = match.group('currency')
            self.buyin = Decimal(match.group('buyin') or 0)
            self.rake = Decimal(match.group('rake') or 0)
        else:
            self.game_type = GameType.CASH
            self.tournament_ident = None
            self.tournament_level = None
            currency = match.group('cash_currency')
            self.buyin = None
            self.rake = None

        if match.group('freeroll') and not currency:
            currency = 'USD'

        if not currency:
            self.extra['money_type'] = MoneyType.PLAY
            self.currency = None
        else:
            self.extra['money_type'] = MoneyType.REAL
            self.currency = Currency(currency)

        self.game = Game(match.group('game'))
        self.limit = Limit(match.group('limit'))

        self._parse_date(match.group('date'))

        self.header_parsed = True

    def parse(self):
        """Parses the body of the hand history, but first parse header if not yet parsed."""
        if not self.header_parsed:
            self.parse_header()

        self._parse_table()
        self._parse_players()
        self._parse_button()
        self._parse_hero()
        self._parse_preflop()
        self._parse_flop()
        self._parse_street('turn')
        self._parse_street('river')
        self._parse_showdown()
        self._parse_pot()
        self._parse_board()
        self._parse_winners()

        self._del_split_vars()
        self.parsed = True

    def _parse_table(self):
        self._table_match = self._table_re.match(self._splitted[1])
        self.table_name = self._table_match.group(1)
        self.max_players = int(self._table_match.group(2))

    def _parse_players(self):
        self.players = self._init_seats(self.max_players)
        for line in self._splitted[2:]:
            match = self._seat_re.match(line)
            # we reached the end of the players section
            if not match:
                break
            index = int(match.group('seat')) - 1
            self.players[index] = hh._Player(
                name=match.group('name'),
                stack=Decimal(match.group('stack')),
                seat=int(match.group('seat')),
                combo=None
            )

    def _parse_button(self):
        button_seat = int(self._table_match.group('button'))
        self.button = self.players[button_seat - 1]

    def _parse_hero(self):
        hole_cards_line = self._splitted[self._sections[0] + 2]
        match = self._hero_re.match(hole_cards_line)
        try:
            hero, hero_index = self._get_hero_from_players(match.group('hero_name'))
            p = re.compile(r'(..\b)')
            cards = re.findall(p, match.group('cards'))
            hero = hero._replace(combo=Combo.from_array(cards))
            self.hero = self.players[hero_index] = hero
            if self.button.name == self.hero.name:
                self.button = hero
        except AttributeError:
            self.hero = None

    def _parse_preflop(self):
        start = self._sections[0] + 3
        stop = self._sections[1]
        ap = ActionParser()
        actions = list()
        for action_str in self._splitted[start:stop]:
            try:
                action = ap.parse(action_str)
                actions.append(action)
            except UnknownActionError as e:
                logger.warning(e.message)

        self.preflop_actions = tuple(actions) if actions else None

    def _parse_flop(self):
        try:
            start = self._splitted.index('FLOP') + 1
        except ValueError:
            self.flop = None
            return
        stop = self._splitted.index('', start)
        floplines = self._splitted[start:stop]
        self.flop = _Street(floplines)
        self.flop_actions = self.flop.actions

    def _parse_street(self, street):
        street_attr = '%s_actions' % street.lower()
        try:
            start = self._splitted.index(street.upper()) + 2
            stop = self._splitted.index('', start)
            ap = ActionParser()

            action_lines = self._splitted[start:stop]
            actions = list()
            for action_str in action_lines:
                try:
                    actions.append(ap.parse(action_str))
                except UnknownActionError as e:
                    logger.warning(e.message)
            setattr(self, street_attr, tuple(actions) if actions else None)
        except ValueError:
            setattr(self, street, None)
            setattr(self, street_attr, None)

    def _parse_showdown(self):
        try:
            start = self._splitted.index('SHOW DOWN') + 1
            stop = self._splitted.index('', start)
            action_lines = self._splitted[start:stop]

            ap = ActionParser()
            actions = list()
            for action_str in action_lines:
                try:
                    actions.append(ap.parse(action_str))
                except UnknownActionError as e:
                    logger.warning(e.message)

            self.show_down = True
            self.show_down_actions = tuple(actions)
        except ValueError:
            self.show_down = False
            self.show_down_actions = None

    def _parse_pot(self):
        potline = self._splitted[self._sections[-1] + 2]
        match = self._pot_re.match(potline)
        self.total_pot = Decimal(match.group(1))

    def _parse_board(self):
        boardline = self._splitted[self._sections[-1] + 3]
        if not boardline.startswith('Board'):
            return
        cards = self._board_re.findall(boardline)
        self.turn = Card(cards[3]) if len(cards) > 3 else None
        self.river = Card(cards[4]) if len(cards) > 4 else None

    def _parse_winners(self):
        winners = set()
        start = self._sections[-1] + 4
        for line in self._splitted[start:]:
            if not self.show_down and "collected" in line:
                match = self._winner_re.match(line)
                winners.add(match.group('name'))
            elif self.show_down and "won" in line:
                match = self._showdown_re.match(line)
                winners.add(match.group('name'))

        self.winners = tuple(winners)


_Label = namedtuple('_Label', 'id, color, name')
"""Named tuple for labels in Player notes."""

_Note = namedtuple('_Note', 'player, label, update, text')
"""Named tuple for player notes."""


class NoteNotFoundError(ValueError):
    """Note not found for player."""


class LabelNotFoundError(ValueError):
    """Label not found in the player notes."""


class Notes(object):
    """Class for parsing pokerstars XML notes."""

    _color_re = re.compile('^[0-9A-F]{6}$')

    def __init__(self, notes):
        # notes need to be a unicode object
        self.raw = notes
        parser = etree.XMLParser(recover=True, resolve_entities=False)
        self.root = etree.XML(notes.encode('utf-8'), parser)

    def __unicode__(self):
        return str(self).decode('utf-8')

    def __str__(self):
        return etree.tostring(self.root, xml_declaration=True, encoding='UTF-8', pretty_print=True)

    @classmethod
    def from_file(cls, filename):
        """Make an instance from a XML file."""
        return cls(Path(filename).open().read())

    @property
    def players(self):
        """Tuple of player names."""
        return tuple(note.get('player') for note in self.root.iter('note'))

    @property
    def label_names(self):
        """Tuple of label names."""
        return tuple(label.text for label in self.root.iter('label'))

    @property
    def notes(self):
        """Tuple of notes wrapped in namedtuples."""
        return tuple(self._get_note_data(note) for note in self.root.iter('note'))

    @property
    def labels(self):
        """Tuple of labels."""
        return tuple(_Label(label.get('id'), label.get('color'), label.text) for label
                     in self.root.iter('label'))

    def get_note_text(self, player):
        """Return note text for the player."""
        note = self._find_note(player)
        return note.text

    def get_note(self, player):
        """Return :class:`_Note` tuple for the player."""
        return self._get_note_data(self._find_note(player))

    def add_note(self, player, text, label=None, update=None):
        """Add a note to the xml. If update param is None, it will be the current time."""
        if label is not None and (label not in self.label_names):
            raise LabelNotFoundError('Invalid label: {}'.format(label))
        if update is None:
            update = datetime.utcnow()
        # converted to timestamp, rounded to ones
        update = update.strftime('%s')
        label_id = self._get_label_id(label)
        new_note = etree.Element('note', player=player, label=label_id, update=update)
        new_note.text = text
        self.root.append(new_note)

    def append_note(self, player, text):
        """Append text to an already existing note."""
        note = self._find_note(player)
        note.text += text

    def prepend_note(self, player, text):
        """Prepend text to an already existing note."""
        note = self._find_note(player)
        note.text = text + note.text

    def replace_note(self, player, text):
        """Replace note text with text. (Overwrites previous note!)"""
        note = self._find_note(player)
        note.text = text

    def change_note_label(self, player, label):
        label_id = self._get_label_id(label)
        note = self._find_note(player)
        note.attrib['label'] = label_id

    def del_note(self, player):
        """Delete a note by player name."""
        self.root.remove(self._find_note(player))

    def _find_note(self, player):
        # if player name contains a double quote, the search phrase would be invalid.
        # &quot; entitiy is searched with ", e.g. &quot;bootei&quot; is searched with '"bootei"'
        quote = "'" if '"' in player else '"'
        note = self.root.find('note[@player={0}{1}{0}]'.format(quote, player))
        if note is None:
            raise NoteNotFoundError(player)
        return note

    def _get_note_data(self, note):
        labels = {label.get('id'): label.text for label in self.root.iter('label')}
        label = note.get('label')
        label = labels[label] if label != "-1" else None
        timestamp = note.get('update')
        if timestamp:
            timestamp = int(timestamp)
            update = datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC)
        else:
            update = None
        return _Note(note.get('player'), label, update, note.text)

    def get_label(self, name):
        """Find the label by name."""
        label_tag = self._find_label(name)
        return _Label(label_tag.get('id'), label_tag.get('color'), label_tag.text)

    def add_label(self, name, color):
        """Add a new label. It's id will automatically be calculated."""
        color_upper = color.upper()
        if not self._color_re.match(color_upper):
            raise ValueError('Invalid color: {}'.format(color))

        labels_tag = self.root[0]
        last_id = int(labels_tag[-1].get('id'))
        new_id = str(last_id + 1)

        new_label = etree.Element('label', id=new_id, color=color_upper)
        new_label.text = name

        labels_tag.append(new_label)

    def del_label(self, name):
        """Delete a label by name."""
        labels_tag = self.root[0]
        labels_tag.remove(self._find_label(name))

    def _find_label(self, name):
        labels_tag = self.root[0]
        try:
            return labels_tag.xpath('label[text()="%s"]' % name)[0]
        except IndexError:
            raise LabelNotFoundError(name)

    def _get_label_id(self, name):
        return self._find_label(name).get('id') if name else '-1'

    def save(self, filename):
        """Save the note XML to a file."""
        with open(filename, 'w') as fp:
            fp.write(str(self))
