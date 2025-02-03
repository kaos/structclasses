structclasses
=============

This is a library for working with binary data protocols.
Building upon `dataclasses` from the Python standard library, as
well as taking inspiration for the API design from the Ruby gem
[bindata](https://rubygems.org/gems/bindata).

The result is a augmented `dataclass` object with to/from binary serialization
capabilities.

install
-------

    pip install structclasses
    
example
-------

```python
from structclasses import structclass, uint8, union, text, binary


@structclass
class DemoHeader:
  example_id: int  # alias for `int32`


@structclass
class Demo:
  field_a: uint8
  header: DemoHeader
  msg: text[32]     # The length may reference a previously defined field for dynamic length objects.
  payload: union[
    'field_a',      # The value of the named field specifies the union type to use. (May be a callable instead for more flexibility.)
    (0, uint8),     # When `field_a` is 0, `payload` is a `uint8`.
    (1, binary[8])  # When `field_a` is 1, `payload` is a `binary[8]`.
  ]

demo = Demo(field_a=0, msg="hello world", header=DemoHeader(123), payload=42)

packed_binary = demo._pack()  # => b'\x00\x00\x00\x00{hello world\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00*'
Demo._unpack(packed_binary) == demo  # => True

```

A `structclass` works as a drop-in substitute for the `dataclass` decorator,
only adding the `_pack()`/`_unpack()` methods to the class for serializing
to/from binary data.

