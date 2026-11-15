"""Adversarial source-bound and recursive-parser regression cases."""
import unittest

from sharkbyte_alpha import vm


class CompilerHardeningTests(unittest.TestCase):
    def test_parenthesis_nesting_fails_with_stable_language_error(self):
        depth = vm.MAX_PARSE_NESTING + 1
        source = "print " + "(" * depth + "1" + ")" * depth + ";"
        with self.assertRaisesRegex(vm.SharkError, "Parse nesting limit exceeded"):
            vm.compile_source(source)

    def test_unary_minus_chain_fails_with_stable_language_error(self):
        depth = vm.MAX_PARSE_NESTING + 1
        source = "print " + "-" * depth + "1;"
        with self.assertRaisesRegex(vm.SharkError, "Parse nesting limit exceeded"):
            vm.compile_source(source)

    def test_left_associative_chains_are_bounded_in_both_compilers(self):
        limit = vm.MAX_EXPRESSION_CHAIN
        accepted_v04 = "print " + "+".join(["1"] * (limit + 1)) + ";"
        accepted_v05 = (
            "fun f() { return " + "+".join(["1"] * (limit + 1))
            + "; } print f();"
        )
        self.assertIsNotNone(vm.compile_source(accepted_v04))
        self.assertIsNotNone(vm.compile_source(accepted_v05))

        rejected_v04 = "print " + "+".join(["1"] * (limit + 2)) + ";"
        rejected_v05 = (
            "fun f() { return " + "+".join(["1"] * (limit + 2))
            + "; } print f();"
        )
        for source in (rejected_v04, rejected_v05):
            with self.subTest(parser="v04" if "fun f" not in source else "v05"):
                with self.assertRaisesRegex(
                    vm.SharkError, "Expression chain limit exceeded"
                ):
                    vm.compile_source(source)

    def test_nested_block_fails_with_stable_language_error(self):
        depth = vm.MAX_PARSE_NESTING + 1
        source = "let x = 1; " + "if (x) { " * depth + "print x; " + "}" * depth
        with self.assertRaisesRegex(vm.SharkError, "Parse nesting limit exceeded"):
            vm.compile_source(source)

    def test_compile_api_enforces_documented_utf8_source_limit(self):
        source = " " * (vm.MAX_SOURCE_BYTES + 1)
        with self.assertRaisesRegex(vm.SharkError, "Source exceeds 65536 UTF-8 bytes"):
            vm.compile_source(source)

    def test_invalid_surrogate_is_a_controlled_language_error(self):
        with self.assertRaisesRegex(vm.SharkError, "Source contains invalid Unicode"):
            vm.compile_source("print \ud800;")


if __name__ == "__main__":
    unittest.main(verbosity=2)
