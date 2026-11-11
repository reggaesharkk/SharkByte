import contextlib, io, json, math, unittest
from sharkbyte_alpha import cli, quantum

def call(args):
    out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):status=cli.main(args)
    return status,out.getvalue(),err.getvalue()

class Toolchain(unittest.TestCase):
    def test_classical_and_integrity(self):
        status,out,_=call(['run','examples/example.sb']);self.assertEqual(status,0);record=json.loads(out)
        self.assertEqual(record['result']['stdout'],'42\n');self.assertEqual(record['result']['vm_instruction_count'],5)
        self.assertEqual(cli.verify(record)['status'],'INTEGRITY_VERIFIED')
        record['result']['stdout']='41\n'
        with self.assertRaises(ValueError):cli.verify(record)
    def test_bell_independent_probabilities(self):
        status,out,_=call(['run','examples/bell.sb','--mode','quantum']);self.assertEqual(status,0);r=json.loads(out)['result']
        for key,expected in {'00':.5,'01':0.,'10':0.,'11':.5}.items():self.assertAlmostEqual(r['probabilities'][key],expected,places=12)
        self.assertEqual(sum(r['counts'].values()),1024)
        self.assertEqual(call(['run','examples/bell.sb','--mode','quantum'])[1],out)
    def test_ghz_independent_probabilities(self):
        circuit=quantum.parse('qubits 3; shots 8; h 0; cx 0 1; cx 1 2; measure_all;')
        state=quantum.evaluate(circuit)['probabilities']
        self.assertAlmostEqual(state['000'],.5,places=12);self.assertAlmostEqual(state['111'],.5,places=12)
        self.assertAlmostEqual(sum(state.values()),1.,places=12)
    def test_cp_matches_hand_calculation(self):
        circuit=quantum.parse('qubits 2; shots 8; h 0; h 1; cp 3.141592653589793 0 1; measure_all;')
        state=quantum.simulate(circuit)
        for i in range(3):self.assertAlmostEqual(abs(state[i]-.5),0.,places=12)
        self.assertAlmostEqual(abs(state[3]+.5),0.,places=12)
    def test_invalid_syntax_and_limits(self):
        with self.assertRaises(ValueError):quantum.parse('qubits 7; measure_all;')
        with self.assertRaises(ValueError):quantum.parse('qubits 2; cx 0 0; measure_all;')
        with self.assertRaises(ValueError):quantum.parse('qubits 2; h 0;')
    def test_native_rejected(self):
        self.assertNotEqual(call(['run','examples/example.sb','--backend','direct_native'])[0],0)
    def test_qasm_generated(self):
        circuit=quantum.parse('qubits 2; h 0; cx 0 1; measure_all;');qasm=quantum.to_qasm(circuit)
        self.assertIn('OPENQASM 3.0;',qasm);self.assertIn('cx q[0], q[1];',qasm)
    def test_vm_step_limit(self):
        binary=cli.vm.encode(*cli.vm.compile_source('let x = 0; while (x < 1) { x = x; }'))
        with self.assertRaises(cli.vm.SharkError):cli.vm.run_vm(binary,max_steps=50)

if __name__=='__main__':unittest.main(verbosity=2)
