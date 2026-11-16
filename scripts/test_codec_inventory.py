import ctypes as c
import unittest

from codec_inventory import Node, NodeList, decode_node, validate_inventory


class InventoryTests(unittest.TestCase):
    def properties(self, drivers):
        return {'decoder-list': [{'codec': codec, 'driver': driver} for codec, driver in drivers],
                'demuxer-lavf-list': ['mov', 'matroska'], 'protocol-list': ['file', 'https']}

    def test_missing_decoder_fails_release_requirement(self):
        with self.assertRaisesRegex(ValueError, 'vvc'):
            validate_inventory(self.properties([('h264', 'h264')]), ['h264', 'vvc'])

    def test_hardware_only_av1_is_not_a_software_floor(self):
        with self.assertRaisesRegex(ValueError, 'software fallback'):
            validate_inventory(self.properties([('av1', 'av1')]), ['av1'])
        actual = validate_inventory(self.properties([('av1', 'av1'), ('av1', 'libdav1d')]), ['av1'])
        self.assertEqual(actual['av1'], ['av1', 'libdav1d'])

    def test_native_node_array_and_map(self):
        values = (Node * 2)()
        values[0].format, values[0].u.string = 1, b'av1'
        values[1].format, values[1].u.string = 1, b'libdav1d'
        keys = (c.c_char_p * 2)(b'codec', b'driver')
        children = NodeList(2, values, keys)
        node = Node()
        node.format, node.u.list = 8, c.pointer(children)
        self.assertEqual(decode_node(node), {'codec': 'av1', 'driver': 'libdav1d'})
        node.format = 7
        self.assertEqual(decode_node(node), ['av1', 'libdav1d'])

    def test_invalid_native_array_fails(self):
        children = NodeList(-1, None, None)
        node = Node()
        node.format, node.u.list = 7, c.pointer(children)
        with self.assertRaises(ValueError):
            decode_node(node)


if __name__ == '__main__':
    unittest.main()
