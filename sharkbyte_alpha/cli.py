"""Local VM and classical statevector CLI; experimental and resource bounded."""
import argparse, hashlib, json, pathlib, platform, re, sys
from . import __version__, vm, quantum

MAX_SOURCE_BYTES=65536
VM_STEPS=50_000_000

def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(obj): return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf8')
def read_source(path):
    p=pathlib.Path(path)
    with p.open('rb') as f:data=f.read(MAX_SOURCE_BYTES+1)
    if len(data)>MAX_SOURCE_BYTES:raise ValueError('source exceeds 65536 UTF-8 bytes')
    return data.decode('utf8')
def parse_quantum(source):
    match=re.fullmatch(r'\s*quantum\s+[A-Za-z_][A-Za-z_0-9]*\s*\{(.*)\}\s*',source,re.DOTALL)
    return quantum.parse(match.group(1) if match else source)
def envelope(source,mode,result,binary=None):
    body={'schema':1,'toolchain_version':__version__,'mode':mode,'source':source,
          'source_sha256':digest(source.encode('utf8')),'result':result}
    if binary is not None:body['bytecode_hex']=binary.hex();body['bytecode_sha256']=digest(binary)
    return {**body,'record_sha256':digest(canonical(body))}
def verify(record):
    if not isinstance(record,dict) or record.get('schema')!=1:raise ValueError('invalid record schema')
    body={k:v for k,v in record.items() if k!='record_sha256'}
    if not isinstance(record.get('record_sha256'),str) or digest(canonical(body))!=record['record_sha256']:raise ValueError('record hash mismatch')
    source=record.get('source')
    if not isinstance(source,str) or digest(source.encode('utf8'))!=record.get('source_sha256'):raise ValueError('source hash mismatch')
    if 'bytecode_hex' in record:
        raw=bytes.fromhex(record['bytecode_hex'])
        if digest(raw)!=record.get('bytecode_sha256'):raise ValueError('bytecode hash mismatch')
    return {'status':'INTEGRITY_VERIFIED','note':'Hashes are unkeyed; verification does not prove authorship or correctness.'}
def main(argv=None):
    parser=argparse.ArgumentParser(prog='sharkbyte');parser.add_argument('--version',action='version',version='SharkByte standalone '+__version__)
    sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('doctor')
    run=sub.add_parser('run');run.add_argument('source');run.add_argument('--mode',choices=('classical','quantum','hybrid'),default='classical');run.add_argument('--backend',default='vm');run.add_argument('--summary',action='store_true',help='print a human summary; requires --output to preserve the full record');run.add_argument('--output',help='create a new UTF-8 JSON execution record')
    qasm=sub.add_parser('qasm');qasm.add_argument('source');qasm.add_argument('--output',required=True)
    v=sub.add_parser('verify-run');v.add_argument('record')
    args=parser.parse_args(argv)
    try:
        if args.command=='doctor':value={'version':__version__,'python':platform.python_version(),'architecture':platform.machine(),'vm_step_limit':VM_STEPS,'native':'disabled','hybrid':'experimental vm'}
        elif args.command=='verify-run':value=verify(json.loads(pathlib.Path(args.record).read_text(encoding='utf8')))
        elif args.command=='qasm':
            source=read_source(args.source);output=quantum.to_qasm(parse_quantum(source));target=pathlib.Path(args.output)
            if target.resolve()==pathlib.Path(args.source).resolve():raise ValueError('output must differ from source')
            with target.open('x',encoding='utf8',newline='\n') as f:f.write(output)
            value={'status':'QASM_WRITTEN','output':str(target),'sha256':digest(output.encode('utf8'))}
        else:
            if args.backend!='vm':raise ValueError('native backends are disabled: containment unavailable')
            source=read_source(args.source)
            if args.mode=='quantum':value=envelope(source,'quantum',quantum.evaluate(parse_quantum(source)))
            elif args.mode=='hybrid':
                from . import hybrid
                value=envelope(source,'hybrid',hybrid.run(source,min(VM_STEPS, hybrid.MAX_VM_STEPS)))
            else:
                binary=vm.encode(*vm.compile_source(source));stats={};output=vm.run_vm(binary,max_steps=VM_STEPS,stats=stats)
                value=envelope(source,'classical',{'stdout':output,'vm_instruction_count':stats.get('instructions_executed'),'vm_step_limit':VM_STEPS},binary)
        encoded=json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False)
        if args.command=='run':
            if args.summary and not args.output:raise ValueError('--summary requires --output to preserve the complete record')
            if args.output:
                target=pathlib.Path(args.output)
                if target.resolve()==pathlib.Path(args.source).resolve():raise ValueError('output must differ from source')
                with target.open('x',encoding='utf8',newline='\n') as f:f.write(encoded+'\n')
            if args.summary:
                result=value['result'];print('Mode: '+args.mode+' | Backend: '+('classical statevector simulator' if args.mode=='quantum' else 'SharkVM + classical statevector simulator' if args.mode=='hybrid' else 'SharkVM'))
                if args.mode=='hybrid':
                    print('Iterations: '+str(result.get('iterations_executed',1)))
                    for row in result.get('history',[]):print('  iteration '+str(row['iteration'])+': count='+str(row['zero_state_count'])+' theta='+str(row['theta']))
                elif args.mode=='classical':print('Output: '+repr(result.get('stdout','')))
                else:print('Qubits: '+str(result.get('qubits'))+' | Shots: '+str(result.get('shots')))
                print('Complete JSON record: '+str(args.output));return 0
        print(encoded);return 0
    except (ValueError,RuntimeError,OSError,UnicodeError,vm.SharkError) as exc:
        print('sharkbyte: '+type(exc).__name__+': '+str(exc),file=sys.stderr);return 1
