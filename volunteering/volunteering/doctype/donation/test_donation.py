import unittest

from volunteering.volunteering.doctype.donation.donation import PAN_RE


class TestDonationPan(unittest.TestCase):
	def test_valid_pan(self):
		self.assertTrue(PAN_RE.match("ABCDE1234F"))

	def test_invalid_pan(self):
		self.assertFalse(PAN_RE.match("ABCDE12345"))
		self.assertFalse(PAN_RE.match("abcde1234f"))
		self.assertFalse(PAN_RE.match(""))
