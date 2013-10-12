from nose_parameterized import parameterized
from nose.tools import assert_equal
import test_data
import unittest
import pytz
from decimal import Decimal
from datetime import datetime
from collections import OrderedDict, MutableMapping
from handparser import PokerStarsHand


ET = pytz.timezone('US/Eastern')


class BaseHeaderTest(unittest.TestCase):
    def setUp(self):
        self.hand = PokerStarsHand(self.hh, parse=False)
        self.hand.parse_header()

    def tearDown(self):
        del self.hand


class BaseBodyTest(unittest.TestCase):
    def setUp(self):
        self.hand = PokerStarsHand(self.hh)

    def tearDown(self):
        del self.hand


class TestHeaderHand2(BaseHeaderTest):
    hh = test_data.HAND2

    @parameterized.expand([('poker_room', 'STARS'),
                           ('ident', '105034215446'),
                           ('game_type', 'TOUR'),
                           ('tournament_ident', '797536898'),
                           ('tournament_level', 'XI'),
                           ('currency', 'USD'),
                           ('buyin', Decimal('3.19')),
                           ('rake', Decimal('0.31')),
                           ('game', 'HOLDEM'),
                           ('limit', 'NL'),
                           ('sb', Decimal(400)),
                           ('bb', Decimal(800)),
                           ('date', ET.localize(datetime(2013, 10, 4, 17, 22, 20))),
    ])
    def test_header(self, attr, res):
        assert_equal(getattr(self.hand, attr), res)


class TestBodyAllinPreflop(BaseBodyTest):
    hh = test_data.HAND2

    @parameterized.expand([('table_name', '797536898 9'),
                           ('max_players', 9),
                           ('button_seat', 2),
                           ('button', 'W2lkm2n'),
                           ('hero', 'W2lkm2n'),
                           ('hero_seat', 2),
                           ('players', OrderedDict([('RichFatWhale', 12910), ('W2lkm2n', 11815), ('Labahra', 7395),
                                                    ('Lean Abadia', 7765), ('lkenny44', 10080), ('Newfie_187', 1030),
                                                    ('Hokolix', 13175), ('pmmr', 2415), ('costamar', 13070)])),
                           ('hero_hole_cards', ('Jd', 'Js')),
                           ('flop', ('3c', '6s', '9d')),
                           ('turn', '8d'),
                           ('river', 'Ks'),
                           ('board', ('3c', '6s', '9d', '8d', 'Ks')),
                           ('preflop_actions', ("lkenny44: folds",
                                                "Newfie_187: raises 155 to 955 and is all-in",
                                                "Hokolix: folds",
                                                "pmmr: folds",
                                                "costamar: raises 12040 to 12995 and is all-in",
                                                "RichFatWhale: folds",
                                                "W2lkm2n: calls 11740 and is all-in",
                                                "Labahra: folds",
                                                "Lean Abadia: folds",
                                                "Uncalled bet (1255) returned to costamar")),
                           ('flop_actions', None),
                           ('turn_actions', None),
                           ('river_actions', None),
                           ('total_pot', Decimal(26310)),
                           ('show_down', True),
                           ('winners', ('costamar',)),
    ])
    def test_body(self, attr, res):
        assert_equal(getattr(self.hand, attr), res)


class TestHeaderHand3(BaseHeaderTest):
    hh = test_data.HAND3

    @parameterized.expand([('poker_room', 'STARS'),
                           ('ident', '105026771696'),
                           ('game_type', 'TOUR'),
                           ('tournament_ident', '797469411'),
                           ('tournament_level', 'X'),
                           ('currency', 'USD'),
                           ('buyin', Decimal('3.19')),
                           ('rake', Decimal('0.31')),
                           ('game', 'HOLDEM'),
                           ('limit', 'NL'),
                           ('sb', Decimal(300)),
                           ('bb', Decimal(600)),
                           ('date', ET.localize(datetime(2013, 10, 4, 14, 50, 56)))
    ])
    def test_header(self, attr, res):
        assert_equal(getattr(self.hand, attr), res)


class TestBodyMissingPlayerNoBoard(BaseBodyTest):
    hh = test_data.HAND3

    @parameterized.expand([('table_name', '797469411 11'),
                           ('max_players', 9),
                           ('button_seat', 8),
                           ('button', 'W2lkm2n'),
                           ('hero', 'W2lkm2n'),
                           ('hero_seat', 8),
                           ('players', OrderedDict([('Empty Seat 1', 0), ('snelle_jel', 4295), ('EuSh0wTelm0', 11501),
                                                    ('panost3', 7014), ('Samovlyblen', 7620), ('Theralion', 4378),
                                                    ('wrsport1015', 9880), ('W2lkm2n', 10714), ('fischero68', 8724)])),
                           ('hero_hole_cards', ('6d', '8d')),
                           ('flop', None),
                           ('turn', None),
                           ('river', None),
                           ('board', None),
                           ('preflop_actions', ('EuSh0wTelm0: folds',
                                                'panost3: folds',
                                                'Samovlyblen: folds',
                                                'Theralion: raises 600 to 1200',
                                                'wrsport1015: folds',
                                                'W2lkm2n: folds',
                                                'fischero68: folds',
                                                'snelle_jel: folds',
                                                'Uncalled bet (600) returned to Theralion',
                                                'Theralion collected 1900 from pot',
                                                "Theralion: doesn't show hand")),
                           ('flop_actions', None),
                           ('turn_actions', None),
                           ('river_actions', None),
                           ('total_pot', Decimal(1900)),
                           ('show_down', False),
                           ('winners', ('Theralion',)),
                           ])
    def test_body(self, attr, res):
        assert_equal(getattr(self.hand, attr), res)


class TestHeaderHand4(BaseHeaderTest):
    hh = test_data.HAND4

    @parameterized.expand([('poker_room', 'STARS'),
                           ('ident', '105025168298'),
                           ('game_type', 'TOUR'),
                           ('tournament_ident', '797469411'),
                           ('tournament_level', 'IV'),
                           ('currency', 'USD'),
                           ('buyin', Decimal('3.19')),
                           ('rake', Decimal('0.31')),
                           ('game', 'HOLDEM'),
                           ('limit', 'NL'),
                           ('sb', Decimal(50)),
                           ('bb', Decimal(100)),
                           ('date', ET.localize(datetime(2013, 10, 4, 14, 19, 17)))
    ])
    def test_header(self, attr, res):
        assert_equal(getattr(self.hand, attr), res)


class TestBodyEveryStreet(BaseBodyTest):
    hh = test_data.HAND4

    @parameterized.expand([('table_name', '797469411 15'),
                           ('max_players', 9),
                           ('button_seat', 5),
                           ('button', 'W2lkm2n'),
                           ('hero', 'W2lkm2n'),
                           ('hero_seat', 5),
                           ('players', OrderedDict([('flettl2', 3000), ('santy312', 5890), ('flavio766', 11010),
                                                    ('strongi82', 2855), ('W2lkm2n', 5145), ('MISTRPerfect', 2395),
                                                    ('blak_douglas', 3000), ('sinus91', 3000), ('STBIJUJA', 1205)])),
                           ('hero_hole_cards', ('Jc', '5c')),
                           ('flop', ('6s', '4d', '3s')),
                           ('turn', '8c'),
                           ('river', 'Kd'),
                           ('board', ('6s', '4d', '3s', '8c', 'Kd')),
                           ('preflop_actions', ('sinus91: folds',
                                                'STBIJUJA: folds',
                                                'flettl2: raises 125 to 225',
                                                'santy312: folds',
                                                'flavio766: folds',
                                                'strongi82: folds',
                                                'W2lkm2n: folds',
                                                'MISTRPerfect: folds',
                                                'blak_douglas: calls 125')),
                           ('flop_actions', ('blak_douglas: checks',
                                             'flettl2: bets 150',
                                             'blak_douglas: calls 150')),
                           ('turn_actions', ('blak_douglas: checks',
                                             'flettl2: bets 250',
                                             'blak_douglas: calls 250')),
                           ('river_actions', ('blak_douglas: checks',
                                              'flettl2: bets 1300',
                                              'blak_douglas: folds',
                                              'Uncalled bet (1300) returned to flettl2',
                                              'flettl2 collected 1300 from pot',
                                              "flettl2: doesn't show hand")),
                           ('total_pot', Decimal(1300)),
                           ('show_down', False),
                           ('winners', ('flettl2',)),
                           ])
    def test_body(self, attr, res):
        assert_equal(getattr(self.hand, attr), res)


class TestPlayerNameStartsWithDot(BaseBodyTest):
    hh = test_data.HAND5

    def test_player_name_with_dot_should_not_fail(self):
        self.assertIn('.prestige.U$', self.hand.players)
        self.assertEqual(self.hand.players['.prestige.U$'], 3000)


class TestClassRepresentation(BaseBodyTest):
    hh = test_data.HAND1

    def test_unicode(self):
        self.assertEqual(u'<PokerStarsHand: STARS hand #105024000105>', unicode(self.hand))

    def test_str(self):
        self.assertEqual('<PokerStarsHand: STARS hand #105024000105>', str(self.hand))
