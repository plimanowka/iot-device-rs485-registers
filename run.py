#!python
import logging as log
import sys
import csv
from pprint import pp as pprint

import registers


def getArg(args, arg, default = None):
    try:
        idx = args.index(arg)
        args.pop(idx)
        return args.pop(idx) if len(args)>idx else default
    except Exception:
        return default

    
def main(args):
    log.basicConfig(format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=getArg(args, '-log_level', log.INFO)) # if cfg.verbose else log.INFO)
    log.debug('RS485 IoT Device registers parser')
    
    if len(args)==0 or len({'-help', '--help'} & set(args))>0:
        log.info(
            f"""R3485 registers def file parser.
               Usage:
                 {sys.argv[0]} [-g GROUPS] [CSV DictReader format params] regs-file.csv
               Where:
                 -groups            -g              - one or more groups combinations, i.e.: "-g main,status&grid,..."
                 -CSV DictReader format params
                    -cols delim     -delimiter D    - i.e "-delimiter ';'"
                 """)
        return None
        
    groups = getArg(args, '-g')    
    fmtparams = dict(filter(lambda e: e[1] is not None, {k: getArg(args, f'-{k}') for k in csv.Dialect.__dict__.keys() if not k.startswith('_')}.items()))
    
    log.debug(f'Loading registers from {args[0]} in groups: {groups}')
    with open(args[0]) as regs:
        regs = registers.read(regs, **fmtparams)
        if groups is not None:
            groups = [set(g.split('&')) for g in groups.split(',') or []]
            regs = [row for row in regs if not groups or len([g for g in groups if g<=row.groups])>0]
        # for r in sorted(regs):
        #     print(f'[ {hex(r.address)}, {r.name}, {r.description}, {r.type.name}, {r.unit or "-"} ]')
        pprint(sorted(regs))

    
if __name__ == '__main__':
    main(sys.argv[1:])