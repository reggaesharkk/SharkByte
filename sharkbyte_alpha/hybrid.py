"""Local adapter around the preserved 8099B hybrid implementation.

The upstream dispatcher is replaced with direct, bounded VM and simulator calls.
The vendored hybrid parser and iteration logic are unchanged.
"""
import hashlib, importlib.util, pathlib, sys, threading
from . import vm, quantum

VENDOR=pathlib.Path(__file__).resolve().parent/'_vendor'
_lock=threading.RLock()

def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError('cannot load audited hybrid module')
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def _initialize():
    # The preserved entry module imports gate2_parent by its historical name.
    previous=sys.modules.get('gate2_parent')
    parent=_load('gate2_parent',VENDOR/'gate2_parent.py')
    try:engine=_load('sharkbyte_standalone_hybrid_8099b',VENDOR/'sharkbyte_8099b.py')
    finally:
        if previous is None:sys.modules.pop('gate2_parent',None)
        else:sys.modules['gate2_parent']=previous
    return engine

MAX_VM_STEPS = 100_000

def run(source,step_limit=MAX_VM_STEPS):
    if not isinstance(source,str) or len(source.encode('utf8'))>65536:raise ValueError('invalid hybrid source')
    if type(step_limit) is not int or not 1<=step_limit<=MAX_VM_STEPS:raise ValueError('invalid VM step limit')
    with _lock:
        engine=_initialize()
        engine.runtime.BACKENDS=('vm',)
        def local_upstream(path,payload=None):
            if path!='/api/run' or not isinstance(payload,dict):raise ValueError('unsupported hybrid adapter call')
            text=payload.get('source')
            if not isinstance(text,str) or len(text.encode('utf8'))>65536:raise ValueError('invalid adapter source')
            source_hash=hashlib.sha256(text.encode('utf8')).hexdigest()
            if payload.get('mode')=='classical':
                if payload.get('backend')!='vm':raise ValueError('native backends disabled')
                binary=vm.encode(*vm.compile_source(text));stats={};output=vm.run_vm(binary,max_steps=step_limit,stats=stats)
                return 200,{'status':'CLASSICAL_EXECUTED','backend':'vm','stdout':output,'source_sha256':source_hash}
            if payload.get('mode')=='quantum':
                from .cli import parse_quantum
                circuit=parse_quantum(text);result=quantum.evaluate(circuit)
                return 200,{'status':'QUANTUM_SIMULATION_VERIFIED','source_sha256':source_hash,'result':result,
                            'openqasm':quantum.to_qasm(circuit),'hardware_used':False}
            raise ValueError('unsupported hybrid adapter mode')
        engine.runtime.upstream=local_upstream
        status,result=engine.execute({'mode':'hybrid','backend':'vm','source':source})
        if status!=200 or not isinstance(result,dict):raise RuntimeError('hybrid execution failed')
        if result.get('status')=='HYBRID_ITERATIVE_EXECUTED':
            for entry in result.get('history',[]):
                nested=entry.get('report',{})
                limitations=nested.get('limitations')
                if isinstance(limitations,list):
                    nested['limitations']=[('This nested executor describes one iteration; bounded iteration is provided by the outer hybrid orchestrator' if item=='No iterative quantum-classical loops yet' else item) for item in limitations]
        return result
