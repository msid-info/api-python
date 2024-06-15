import unittest
from main import get

class TestGet(unittest.TestCase):
    def test_dict_string_key(self):
        dictionary = {
            "key1": {
                "key2": {
                    "key3": "value"
                }
            }
        }
        key = ["key1", "key2", "key3"]
        expected = "value"
        result = get(dictionary, key)
        self.assertEqual(result, expected)

    def test_dict_int_key(self):
        dictionary = {
            "key1": [
                {
                    "key2": "value1"
                },
                {
                    "key2": "value2"
                }
            ]
        }
        key = ["key1", 1, "key2"]
        expected = "value2"
        result = get(dictionary, key)
        self.assertEqual(result, expected)

    def test_list_int_key(self):
        dictionary = [
            {
                "key1": "value1"
            },
            {
                "key1": "value2"
            }
        ]
        key = [1, "key1"]
        expected = "value2"
        result = get(dictionary, key)
        self.assertEqual(result, expected)

    def test_invalid_key(self):
        dictionary = {
            "key1": {
                "key2": "value"
            }
        }
        key = ["key1", "key3"]
        expected = None
        result = get(dictionary, key)
        self.assertEqual(result, expected)

    def test_invalid_key_type(self):
        dictionary = {
            "key1": {
                "key2": "value"
            }
        }
        key = ["key1", 1, "key2"]
        expected = None
        result = get(dictionary, key)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main() 