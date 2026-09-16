import unittest
from types import SimpleNamespace

from arabic_nameplate.parameters import DEFAULTS, PARAMETERS, parameters_from_object, validate_parameters


class Quantity:
    def __init__(self, value):
        self.Value = value


class ParameterTests(unittest.TestCase):
    def test_schema_names_are_unique_and_defaults_are_valid(self):
        names = [spec["name"] for spec in PARAMETERS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(DEFAULTS), set(names))
        self.assertEqual(validate_parameters(DEFAULTS), [])

    def test_defaults_match_requested_print_profile(self):
        self.assertEqual(DEFAULTS["Text"], "مرحباً")
        self.assertEqual(DEFAULTS["FontSize"], 20.0)
        self.assertGreater(DEFAULTS["TextHeight"], DEFAULTS["OutlineHeight"])
        self.assertEqual(DEFAULTS["OutlineWidth"], 1.2)
        self.assertEqual(DEFAULTS["BaseStyle"], "None")
        self.assertEqual(DEFAULTS["ConnectionMode"], "Bridges")
        self.assertEqual(DEFAULTS["ConnectionScope"], "All")

    def test_quantity_extraction_is_freecad_independent(self):
        values = dict(DEFAULTS)
        values["FontSize"] = Quantity(31.5)
        values["Direction"] = "RTL"
        extracted = parameters_from_object(SimpleNamespace(**values))
        self.assertEqual(extracted["FontSize"], 31.5)
        self.assertIsInstance(extracted["FontSize"], float)
        self.assertEqual(extracted["Direction"], "RTL")

    def test_invalid_values_are_reported_together(self):
        params = dict(DEFAULTS, Text="  ", Alignment="Justified", FontSize=0, CurveTolerance=float("nan"))
        message = " ".join(validate_parameters(params))
        self.assertIn("Text cannot be empty", message)
        self.assertIn("Alignment must be one of", message)
        self.assertIn("Font size must be at least", message)
        self.assertIn("Curve tolerance must be a finite number", message)

    def test_invalid_types_do_not_raise(self):
        params = dict(DEFAULTS, Bold="yes", LineSpacing="wide", BridgeWidth="narrow")
        errors = validate_parameters(params)
        self.assertIn("Bold must be true or false.", errors)
        self.assertIn("Line spacing must be a number.", errors)
        self.assertIn("Bridge width must be a number.", errors)

    def test_mapping_extraction_fills_defaults(self):
        extracted = parameters_from_object({"Text": "سلام", "TextHeight": Quantity(4)})
        self.assertEqual(extracted["Text"], "سلام")
        self.assertEqual(extracted["TextHeight"], 4.0)
        self.assertEqual(extracted["OutlineWidth"], DEFAULTS["OutlineWidth"])


if __name__ == "__main__":
    unittest.main()
