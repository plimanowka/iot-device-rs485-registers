from enum import Enum, IntFlag
from dataclasses import dataclass, field, fields, make_dataclass
from typing import Union
from struct import calcsize
import csv
import re
import locale
from functools import reduce

class RegisterType(Enum):
    def __new__(cls, value, format = None):
        obj = object.__new__(cls)
        obj._value_ = value
        obj._fmt_char = format
        return obj
    
    @property
    def format(self):
        return self._fmt_char
    
    @property
    def size(self):
        return self.get_size()
    
    def get_size(self, len: int = 1):
        return calcsize(self.format) * len
    
    def get_format_str(self, len: int = 1):
        return f'{len}{self.format}'
    
    _ignore_ = 'types_map idx FT k v n'
    
    FT = vars()
    types_map = {
        'h': ['i16', 'int16'], 'H': ['u16', 'uint16'],
        'i': ['int', 'i32', 'int32'], 'I': ['uint', 'u32', 'uint32'],
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

    
@dataclass(order=True)
class RegisterDef:
    address: int = field(compare=True)
    name: str
    type: RegisterType
    len: int
    unit: Union[str, Enum]
    groups: set[str] # = field(default_factory=set)
    divisor: float # = 1.0
    desc: dict[str, str] # = field(default_factory=dict)
    
    @property
    def description(self) -> str:
        return self.get_description()
    
    def get_description(self, lang: str = locale.getdefaultlocale()[0]) -> str:
        return self.desc.get(locale.normalize(lang), self.name)
    
    
def _parse_unit(field: str, field_subtype: str, unit: str):
    field_subtype = field_subtype.upper()
    if field_subtype in {'ENUM', 'FLAGS'}:
        lines = [tuple(re.split(r':[\s]*', l.strip())) for l in unit.splitlines() if l.strip() not in {'', '{', '}'}]
        members = [(name, int(idx, 0)) for (idx, name) in lines]
        return Enum(field, members) if field_subtype == 'ENUM' else IntFlag(field, members)
    else:
        return unit    


_def_field_supplier = lambda row, col: { c: _def_field_supplier(row, cdef) for c, cdef in col.items() } if isinstance(col, dict) else row[col]

_rec_field_suppliers = {
    'address': lambda row, col: int(row['address'], 0),
    'name': lambda row, col: row['name'],
    'type': lambda row, col: RegisterType[row['type'].split(':')[0]],
    'len': lambda row, col: int((row['type'].split(':') + [ '', '' ])[1] or '1'),
    'unit': lambda row, col: _parse_unit(row['name'], (row['type'].split(':') + [ '', '' ])[2], row['unit']),
    'groups': lambda row, col: set(re.findall(r'(\w+)[,]?', row.get('groups', 'all'))),
    'desc': lambda row, col: { l: row[lcol] for l, lcol in col.items() } if set(col.values()) & set(row.keys()) else None
}


def _get_dataclass_and_factory(name, columns, suppliers = {}, base = None):
    sups = {}
    defined_columns = [f.name for f in fields(base)] if base else []

    new_columns = []
    for c, cdef in columns.items():
        supplier = suppliers.get(c, _def_field_supplier)
        supplier = (lambda supplier, cdef: lambda row: supplier(row, cdef))(supplier, cdef)
        if c not in defined_columns:
            if isinstance(cdef, dict):
                cdc, supplier = _get_dataclass_and_factory(f'{c.capitalize()}Rec', cdef)
                new_columns.append((c, cdc))
            else:
                new_columns.append(c)
        sups[c] = supplier

    for c in set(suppliers.keys()) - set(sups.keys()):
        supplier = suppliers.get(c, _def_field_supplier)
        supplier = (lambda supplier, cdef: lambda row: supplier(row, cdef))(supplier, cdef)
        sups[c] = supplier
                
    cdc = make_dataclass(name, new_columns, bases=(base if base else object, ))
    supplier = (lambda cdc, suppliers: lambda row: cdc(**{ k: sup(row) for k, sup in suppliers.items() }))(cdc, sups)
    return (cdc, supplier)


def _parse_column(fname, fdef, acc):
    (field, sep, subfield) = fdef.partition('.')
    acc[field] = _parse_column(fname, subfield, acc.get(field, {})) if subfield else fname
    return acc


def read(file, lang = None, **fmtparams) -> RegisterDef:
    dr = csv.DictReader(file, **fmtparams)
    columns = {}
    for c in sorted(dr.fieldnames):
        columns = _parse_column(c.lower(), c, columns)
    
    assert {'address', 'name', 'type', 'unit'}.issubset(set(columns.keys())), \
        "One or more required columns is missing: 'address', 'name', 'type', 'unit'"
    
    if 'desc' in columns:
        columns['desc'] = { locale.normalize(k.lower()): v for k,v in columns['desc'].items() }

    reg_dataclass, factory = _get_dataclass_and_factory('ModbusRegister', columns, _rec_field_suppliers, RegisterDef)
    
    registers = []
    line = 1
    for row in dr:
        if row['address'] and row['name'] and row['type'] :
            try:
                registers.append(factory(row))
            except Exception as e:
                raise ValueError(f'Error while parsing line {line} of registers definitions CSV') from e
        line += 1
            
    return registers