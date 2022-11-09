from enum import Enum, IntFlag
from dataclasses import dataclass, field
from typing import Union
import struct
import csv
import re
import locale

class FieldType(Enum):
    def __new__(cls, value, format = None):
        obj = object.__new__(cls)
        obj._value_ = value
        obj._fmt_char = format
        return obj
    
    @property
    def format(self):
        return self._fmt_char
    
    def get_size(self, len: int = 1):
        return struct.calcsize(self.format) * len
    
    def get_format_str(self, len: int = 1):
        return f'{len}{self.format}'
    
    _ignore_ = 'types_map idx FT k v n'
    
    FT = vars()
    types_map = {
        'h': ['i16', 'int16'], 'H': ['u16', 'uint16'],
        'i': ['int', 'i32', 'int32'], 'I': ['uint', 'u32'],
        'l': ['long', 'i64', 'int64'], 'L': ['u64', 'uint64'],
        'f': ['float', 'f32', 'f'], 
        'd': ['double', 'f64', 'd'],
        'B': ['bitmap', 'bits'],
        's': ['ascii', 'char'] 
    }
    idx = 0    
    for k, v in types_map.items():
        idx += 1
        for n in v:
            FT[n.upper()] = (idx, k)
    
@dataclass(order=True, frozen=True)
class RegisterDef:
    address: int = field(compare=True)
    name: str
    type: FieldType
    len: int
    unit: Union[str, Enum]
    groups: set[str] = field(default_factory=set)
    divisor: float = 1.0
    desc: dict[str, str] = field(default_factory=dict)
    
    @property
    def description(self):
        return self.get_description()
    
    def get_description(self, lang: str = locale.getdefaultlocale()[0]) -> str:
        return self.desc.get(locale.normalize(lang), self.name)
    
    
def assertHasKeys(dict, keys, dictName = None):
    assert set(keys).issubset(dict), \
        f'{"Missing" if dictName is None else f"{dictName} is missing"} one or more required columns: {", ".join(keys)}'
        
def parseUnit(field: str, field_subtype: str, unit: str):
    field_subtype = field_subtype.upper()
    if field_subtype in {'ENUM', 'FLAGS'}:
        lines = [tuple(re.split(r':[\s]*', l.strip())) for l in unit.splitlines() if l.strip() not in {'', '{', '}'}]
        members = [(name, int(idx, 0)) for (idx, name) in lines]
        return Enum(field, members) if field_subtype == 'ENUM' else IntFlag(field, members)
    else:
        return unit    

def read(file, lang = None, **fmtparams):
    registers = []
    line = 0
    desc_locales = {}
    for row in csv.DictReader(file, **fmtparams):
        if line == 0: 
            assertHasKeys(row, ['address', 'name', 'type', 'unit'], file)
            desc_locales = { locale.normalize(col[5:].lower()): col for col in row.keys() if col.lower().startswith('desc_') }
        line += 1
        if row['address'] and row['name'] and row['type'] :
            try:
                (f_type, f_len, f_subtype) = tuple((row['type'].split(':') + [ '', '' ])[0:3])
                registers.append(RegisterDef(
                    int(row['address'], 0),
                    row['name'],
                    FieldType[f_type.upper()],
                    int(f_len or "1"),
                    parseUnit(row['name'], f_subtype, row['unit']),
                    set(re.findall(r'(\w+)[,]?', row.get('groups', 'all'))),
                    int(row.get('divisor', '') or '1', 0),
                    { locale: row[col] for locale, col in desc_locales.items() if row[col] }
                ))
            except:
                raise BaseException(f'Error while parsing line {line} of {file}')
            
    return registers