import subprocess
import unittest


class TestCliSmoke(unittest.TestCase):
    def test_main_help(self):
        result = subprocess.run(["ltsbikeplan", "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("LTSBikePlan command line interface", result.stdout)

    def test_doctor_help(self):
        result = subprocess.run(["ltsbikeplan", "doctor", "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: ltsbikeplan doctor", result.stdout)

    def test_doctor_exec(self):
        result = subprocess.run(["ltsbikeplan", "doctor", "--city", "Trento, Italy"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Manual required inputs:", result.stdout)


if __name__ == "__main__":
    unittest.main()
