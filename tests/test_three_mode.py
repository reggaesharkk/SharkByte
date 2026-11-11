import cmath, math, pathlib, unittest
from unittest import mock
from sharkbyte_alpha import hybrid, quantum
from sharkbyte_alpha.cli import parse_quantum

class ThreeMode(unittest.TestCase):
    def test_adaptive_feedback_and_analytic_probabilities(self):
        source=pathlib.Path('examples/adaptive.sb').read_text(encoding='utf8').replace('count_00 < 1750','count_00 < 1500')
        with mock.patch('socket.create_connection',side_effect=AssertionError('network access is forbidden')):
            result=hybrid.run(source)
        self.assertEqual(result['iterations_executed'],4)
        self.assertEqual([x['zero_state_count'] for x in result['history']],[906,1250,1675,1666])
        self.assertEqual([x['condition_result'] for x in result['history']],[True,True,False,False])
        for row in result['history']:
            expected=(5+3*math.cos(row['theta']))/8
            self.assertAlmostEqual(row['zero_state_probability'],expected,places=12)
        self.assertEqual(hybrid.run(source)['history'],result['history'])
    def test_historical_six_qubit_qft_against_dft(self):
        source=pathlib.Path('examples/qft_basis_37.sbq').read_text(encoding='utf8')
        state=quantum.simulate(parse_quantum(source))
        error=max(abs(value-cmath.exp(2j*math.pi*37*k/64)/8) for k,value in enumerate(state))
        self.assertLess(error,3e-14)
    def test_historical_qft_inverse_recovers_basis(self):
        source=pathlib.Path('examples/inverse_basis_37.sbq').read_text(encoding='utf8')
        state=quantum.simulate(parse_quantum(source))
        self.assertLess(max(abs(value-(1 if k==37 else 0)) for k,value in enumerate(state)),3e-14)
    def test_five_bit_phase_estimation(self):
        # Eigenstate |1> on qubit 5; controlled phases encode 7/32.
        count=5;measure=7;forward=[]
        for target in reversed(range(count)):
            forward.append(('h',target))
            for control in reversed(range(target)):
                forward.append(('cp',math.pi/(2**(target-control)),control,target))
        for i in range(count//2):
            j=count-1-i;forward.extend([('cx',i,j),('cx',j,i),('cx',i,j)])
        lines=['qubits 6','shots 32','seed 42','x 5']
        lines.extend('h '+str(j) for j in range(count))
        for j in range(count):
            angle=math.remainder(2*math.pi*measure*(2**j)/32,2*math.pi)
            lines.append('cp %.17f %d 5'%(angle,j))
        for op in reversed(forward):
            lines.append(('cp %.17f %d %d'%(-op[1],op[2],op[3])) if op[0]=='cp' else ' '.join(map(str,op)))
        lines.append('measure_all');state=quantum.simulate(quantum.parse(';'.join(lines)+';'))
        target=(1<<5)+measure
        self.assertLess(max(abs(abs(v)**2-(1 if i==target else 0)) for i,v in enumerate(state)),1e-12)

if __name__=='__main__':unittest.main(verbosity=2)
