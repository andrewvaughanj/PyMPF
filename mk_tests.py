#!/usr/bin/env python
##############################################################################
##                                                                          ##
##                                PYMPF                                     ##
##                                                                          ##
##              Copyright (C) 2016-2017, Altran UK Limited                  ##
##              Copyright (C) 2018,      Florian Schanda                    ##
##                                                                          ##
##  This file is part of PyMPF.                                             ##
##                                                                          ##
##  PyMPF is free software: you can redistribute it and/or modify           ##
##  it under the terms of the GNU General Public License as published by    ##
##  the Free Software Foundation, either version 3 of the License, or       ##
##  (at your option) any later version.                                     ##
##                                                                          ##
##  PyMPF is distributed in the hope that it will be useful,                ##
##  but WITHOUT ANY WARRANTY; without even the implied warranty of          ##
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           ##
##  GNU General Public License for more details.                            ##
##                                                                          ##
##  You should have received a copy of the GNU General Public License       ##
##  along with PyMPF. If not, see <http://www.gnu.org/licenses/>.           ##
##                                                                          ##
##############################################################################

# This is the main testcase generator.

import os
import shutil
import random
import argparse
from glob import glob

from mpf.bitvector import *
from mpf.floats import *
from mpf.rationals import *
from mpf.interval_q import *
from evaluator import (fp_eval_predicate,
                       fp_eval_function,
                       is_rounding,
                       all_ops_where,
                       TYP_BOOL, TYP_BV, TYP_REAL, TYP_FLOAT)
from out_smtlib import *

##############################################################################
# Random floats
##############################################################################

def random_zero(eb, sb, sign=0):
    rv = MPF(eb, sb)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        rv.set_zero(0)
    else:
        rv.set_zero(1)
    return rv

def random_subnormal(eb, sb, sign=0):
    rv = MPF(eb, sb)
    S = (0 if sign > 0 or (sign == 0 and random.getrandbits(1) == 0) else 1)
    E = 0
    T = random.randrange(1, 2 ** rv.t)
    rv.pack(S, E, T)
    return rv

def random_normal(eb, sb, sign=0):
    rv = MPF(eb, sb)
    S = (0 if sign > 0 or (sign == 0 and random.getrandbits(1) == 0) else 1)
    E = random.randrange(1, 2 ** rv.w - 1)
    T = random.randrange(0, 2 ** rv.t)
    rv.pack(S, E, T)
    return rv

def random_infinite(eb, sb, sign=0):
    rv = MPF(eb, sb)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        rv.set_infinite(0)
    else:
        rv.set_infinite(1)
    return rv

def random_nan(eb, sb):
    rv = MPF(eb, sb)
    S = random.getrandbits(1)
    E = 2 ** rv.w - 1
    T = random.randrange(1, 2 ** rv.t)
    rv.pack(S, E, T)
    return rv

def smallest_subnormal(eb, sb, sign=0):
    rv = MPF(eb, sb)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        S = 0
    else:
        S = 1
    E = 0
    T = 1
    rv.pack(S, E, T)
    return rv

def largest_subnormal(eb, sb, sign=0):
    rv = MPF(eb, sb)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        S = 0
    else:
        S = 1
    E = 0
    T = 2 ** rv.t - 1
    rv.pack(S, E, T)
    return rv

def smallest_normal(eb, sb, sign=0):
    rv = MPF(eb, sb)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        S = 0
    else:
        S = 1
    E = 1
    T = 0
    rv.pack(S, E, T)
    return rv

def largest_normal(eb, sb, sign=0):
    rv = MPF(eb, sb)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        S = 0
    else:
        S = 1
    E = 2 ** rv.w - 2
    T = 2 ** rv.t - 1
    rv.pack(S, E, T)
    return rv

def random_halfpoint(eb, sb, sign=0):
    # Returns something.5 which is great to test various tie-breaks things
    # involving integers.
    rv = MPF(eb, sb)
    i = random.randint(0, 2 ** (rv.p - 1) - 1)
    rv.from_rational(RM_RNE, Rational(i * 2 + 1, 2))
    rv.set_sign_bit(sign < 0 or (sign == 0 and random.getrandbits(1) == 0))
    return rv

def ubv_boundary(eb, sb, bv_width, sign=0):
    bv = BitVector(bv_width)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        q = Rational(bv.max_unsigned)
    else:
        q = Rational(bv.min_unsigned)
    rv = MPF(eb, sb)
    rv.from_rational(RM_RNE, q)
    return rv

def sbv_boundary(eb, sb, bv_width, sign=0):
    bv = BitVector(bv_width)
    if sign > 0 or (sign == 0 and random.getrandbits(1) == 0):
        q = Rational(bv.max_signed)
    else:
        q = Rational(bv.min_signed)
    rv = MPF(eb, sb)
    rv.from_rational(RM_RNE, q)
    return rv

##############################################################################
# Random rationals
##############################################################################

def random_rational(low, high):
    if low.kind == KIND_INFINITE:
        assert high.kind != KIND_INFINITE
        factor = min(10000, high.value.b ** 3)
        high_a = high.value.a * factor
        b      = high.value.b * factor

        if high.kind == KIND_EXCLUSIVE:
            high_a -= 1

        a = random.randint(-abs(high_a) - abs(factor), high_a)
        return Rational(a, b)

    elif high.kind == KIND_INFINITE:
        factor = min(10000, low.value.b ** 3)
        low_a = low.value.a * factor
        b     = low.value.b * factor

        if low.kind == KIND_EXCLUSIVE:
            low_a += 1

        a = random.randint(low_a, abs(low_a) + abs(factor))
        return Rational(a, b)

    else:
        if low.value < high.value:
            factor = 25
            low_a = low.value.a * high.value.b * factor
            high_a = high.value.a * low.value.b * factor
            b = low.value.b * high.value.b * factor

            if low.kind == KIND_EXCLUSIVE:
                low_a += 1
            if high.kind == KIND_EXCLUSIVE:
                high_a -= 1
            a = random.randint(low_a, high_a)
            return Rational(a, b)
        else:
            return low.value


##############################################################################
# Testvector generation
##############################################################################

def gen_rm(fp_ops):
    if is_rounding(fp_ops):
        for rm in MPF.ROUNDING_MODES:
            yield rm
    else:
        yield RM_RNE

def gen_precisions():
    yield (8, 24)

def gen_vectors(fp_ops, n, test_dup):
    assert n >= 1
    assert test_dup >= 1

    CONSTRUCTORS = {
        "-0"         : lambda eb, sb: random_zero(eb, sb, -1),
        "+0"         : lambda eb, sb: random_zero(eb, sb, 1),
        "-minsub"    : lambda eb, sb: smallest_subnormal(eb, sb, -1),
        "+minsub"    : lambda eb, sb: smallest_subnormal(eb, sb, 1),
        "-subnormal" : lambda eb, sb: random_subnormal(eb, sb, -1),
        "+subnormal" : lambda eb, sb: random_subnormal(eb, sb, 1),
        "-maxsub"    : lambda eb, sb: largest_subnormal(eb, sb, -1),
        "+maxsub"    : lambda eb, sb: largest_subnormal(eb, sb, 1),
        "-minnormal" : lambda eb, sb: smallest_normal(eb, sb, -1),
        "+minnormal" : lambda eb, sb: smallest_normal(eb, sb, 1),
        "-normal"    : lambda eb, sb: random_normal(eb, sb, -1),
        "+normal"    : lambda eb, sb: random_normal(eb, sb, 1),
        "-halfpoint" : lambda eb, sb: random_halfpoint(eb, sb, -1),
        "+halfpoint" : lambda eb, sb: random_halfpoint(eb, sb, 1),
        "-maxnormal" : lambda eb, sb: largest_normal(eb, sb, -1),
        "+maxnormal" : lambda eb, sb: largest_normal(eb, sb, 1),
        "-inf"       : lambda eb, sb: random_infinite(eb, sb, -1),
        "+inf"       : lambda eb, sb: random_infinite(eb, sb, 1),
        "nan"        : lambda eb, sb: random_nan(eb, sb),
    }
    if fp_ops in ("fp.to.ubv", "fp.to.sbv"):
        for k in ("-minsub", "+minsub",
                  "-maxsub", "+maxsub"):
            del CONSTRUCTORS[k]
        CONSTRUCTORS["-sbv_8_bound"] = lambda eb, sb: sbv_boundary(eb, sb, 8, -1)
        CONSTRUCTORS["+sbv_8_bound"] = lambda eb, sb: sbv_boundary(eb, sb, 8, 1)
        CONSTRUCTORS["+ubv_8_bound"] = lambda eb, sb: ubv_boundary(eb, sb, 8, 1)

    TARGETS   = tuple(sorted(list(CONSTRUCTORS)))
    N_TARGETS = len(TARGETS)

    history = set()

    def mk_float(eb, sb, c):
        assert 0 <= c < N_TARGETS
        return CONSTRUCTORS[TARGETS[c]](eb, sb)

    for eb, sb in gen_precisions():
        for rm in gen_rm(fp_ops):
            classes = [0] * n
            while True:
                text = map(lambda x: TARGETS[x], classes)
                for test_index in xrange(test_dup):
                    # Seed each test the same way, so that when we
                    # re-build tests with new constructors, the existing
                    # ones don't change.
                    #
                    # TODO: Add a command-line flag to change the core
                    # seed.
                    seed_str = "__".join(text + [str(test_index)])
                    random.seed(seed_str)

                    # Create test.
                    v_exp = random.choice(["sat", "unsat"])
                    v_val = map(lambda c: mk_float(eb, sb, c), classes)
                    h     = tuple([v_exp] + [rm] + map(lambda x: x.bv, v_val))
                    comment = "(" + fp_ops
                    if is_rounding(fp_ops):
                        comment += " " + rm
                    comment += " "
                    comment += " ".join(text)
                    comment += ")"
                    if h not in history:
                        history.add(h)
                        yield {
                            "ops"         : fp_ops,
                            "rounding"    : rm,
                            "expectation" : v_exp,
                            "values"      : v_val,
                            "comment"     : comment,
                            "raw_kinds"   : text,
                        }

                # Select the next class of test to produce.
                k = n - 1
                while (k >= 0):
                    if classes[k] < (N_TARGETS - 1):
                        classes[k] += 1
                        break
                    else:
                        assert classes[k] == (N_TARGETS - 1)
                        classes[k] = 0
                        k -= 1
                if k == -1:
                    break

def gen_bv_vectors(fp_ops, n, test_dup):
    assert n == 1

    for bv_width in (8, 16, 32, 64, 128):
        bv = BitVector(bv_width)
        comment = "%s(BitVec %u)" % (fp_ops, bv_width)
        for bit_0 in (0, 1):
            bv.bv[0] = bit_0
            for bit_1 in (0, 1):
                bv.bv[1] = bit_1
                for bit_penultimate in (0, 1):
                    bv.bv[-2] = bit_penultimate
                    for bit_last in (0, 1):
                        bv.bv[-1] = bit_last
                        for rm in gen_rm(fp_ops):
                            # Zeros in middle
                            bv.bv[2:-2] = [0] * (bv_width - 4)
                            yield {
                                "ops"         : fp_ops,
                                "rounding"    : rm,
                                "expectation" : random.choice(["sat", "unsat"]),
                                "values"      : [bv],
                                "comment"     : comment,
                            }

                            # Ones in middle
                            bv.bv[2:-2] = [1] * (bv_width - 4)
                            yield {
                                "ops"         : fp_ops,
                                "rounding"    : rm,
                                "expectation" : random.choice(["sat", "unsat"]),
                                "values"      : [bv],
                                "comment"     : comment,
                            }

                            # Random in middle
                            for _ in xrange(test_dup):
                                for b in xrange(2, 2 + bv_width - 4):
                                    bv.bv[b] = random.randint(0, 1)
                                yield {
                                    "ops"         : fp_ops,
                                    "rounding"    : rm,
                                    "expectation" : random.choice(["sat",
                                                                   "unsat"]),
                                    "values"      : [bv],
                                    "comment"     : comment,
                                }

def gen_int_vectors(fp_ops, n, test_dup):
    assert fp_ops == "fp.from.int"
    assert n      == 1

    vec = {
        "ops"         : fp_ops,
        "rounding"    : None,
        "expectation" : None,
        "values"      : None,
        "mpf_fmt"     : None,
        "comment"     : None,
    }

    constructors = ("zero",           # 0
                    "precise_int",    # [1; 2^sb]
                    "rounded_int",    # ]2^sb+1; inf[ (excluding halfpoints)
                    "halfpoint_int",  # ]2^sb; inf[ (halfpoints)
                    "inf_boundary",   # [inf; inf]
                    "inf")            # ]inf; oo[

    def mk_int_halfpoint(eb, sb, n):
        assert n >= 2 ** sb
        q = Rational(n)

        f = MPF(eb, sb)
        f.from_rational(RM_RTZ, q)
        assert f.isIntegral()

        q_1 = f.to_rational()
        assert q_1.isIntegral()

        g = fp_nextUp(f)
        if g.isInfinite():
            g = fp_nextDown(f)
        assert g.isIntegral()

        q_2 = g.to_rational()
        assert q_2.isIntegral()

        hp = (q_1 + q_2) * Rational(1, 2)
        assert hp.isIntegral()

        return hp.to_python_int()


    for rm in gen_rm(fp_ops):
        vec["rounding"] = rm

        for eb, sb in [(8, 24), (11, 53)]:
            vec["mpf_fmt"] = (eb, sb)
            fmt            = MPF(eb, sb)
            inf            = fmt.inf_boundary()

            history = set()

            for cls in constructors:
                vec["comment"] = "(%s %s %s)" % (fp_ops, rm, cls)

                for i in xrange(test_dup):
                    vec["expectation"] = random.choice(["sat", "unsat"])
                    vec["values"]      = None

                    if cls == "zero":
                        vec["values"] = 0
                    elif cls == "precise_int":
                        vec["values"] = random.randint(1, 2 ** sb)
                    elif cls == "rounded_int":
                        # 2 ^ sb .. 2 ^ sb + 1 are all halfpoints or exact
                        n = random.randint((2 ** (sb + 1)) + 1, inf - 1)
                        hp = mk_int_halfpoint(eb, sb, n)
                        vec["values"] = n + random.choice([-1, 1])
                    elif cls == "halfpoint_int":
                        q = random.randint((2 ** sb) + 1, inf - 1)
                        vec["values"] = mk_int_halfpoint(eb, sb, q)
                    elif cls == "inf_boundary":
                        vec["values"] = inf
                    elif cls == "inf":
                        vec["values"] = inf + random.randint(1, inf)
                    assert vec["values"] is not None

                    if random.choice([False, True]):
                        vec["values"] = -vec["values"]

                    if vec["values"] not in history:
                        history.add(vec["values"])
                        yield vec


##############################################################################
# Test generation
##############################################################################

test_id = {}

def new_test(testvec):
    global test_id

    if not os.path.exists(testvec["ops"]):
        os.mkdir(testvec["ops"])

    test_id[testvec["ops"]] = test_id.get(testvec["ops"], 0) + 1

    test_name = testvec["ops"]
    if test_name.startswith("fp."):
        test_name = test_name[3:]
    if is_rounding(testvec["ops"]):
        test_name += "_" + testvec["rounding"].lower()
    test_name += "_%05u.smt2" % test_id[testvec["ops"]]

    print ">>> Generating test %u %s" % (test_id[testvec["ops"]],
                                         testvec["comment"])
    return open(os.path.join(testvec["ops"], test_name), "w")


def mk_tests_for_classify(num_tests):
    for fp_ops in all_ops_where(arity=1, result=TYP_BOOL):
        # check if X is correctly classified
        for vec in gen_vectors(fp_ops, 1, num_tests):
            x      = vec["values"][0]
            result = fp_eval_predicate(fp_ops, x)

            with new_test(vec) as fd:
                smt_write_header(fd, vec["expectation"])
                smt_write_vars(fd, vec)
                smt_write_var(fd, "result", "Bool",
                              "(= result (%s x))" % smt_opsname(fp_ops))
                smt_write_goal(fd, "result", vec["expectation"], result)
                smt_write_footer(fd)

def mk_tests_for_unary(num_tests):
    for fp_ops in all_ops_where(arity=1, args=TYP_FLOAT, result=TYP_FLOAT):
        if fp_ops == "fp.cast":
            continue

        # pick x. compute op(x) = result. check result
        for vec in gen_vectors(fp_ops, 1, num_tests):
            x      = vec["values"][0]
            result = fp_eval_function(fp_ops, vec["rounding"], x)

            with new_test(vec) as fd:
                smt_write_header(fd, vec["expectation"])
                smt_write_vars(fd, vec)
                if is_rounding(fp_ops):
                    smt_write_var(fd, "result", result.smtlib_sort(),
                                  "(= result (%s %s x))" % (smt_opsname(fp_ops),
                                                            vec["rounding"]))
                else:
                    smt_write_var(fd, "result", result.smtlib_sort(),
                                  "(= result (%s x))" % smt_opsname(fp_ops))
                smt_write_goal(fd,
                               "(= result %s)" % result.smtlib_random_literal(),
                               vec["expectation"])
                smt_write_footer(fd)

        # pick result. compute op(x) = result. check x
        # TODO

def mk_tests_for_relations(num_tests):
    for fp_ops in all_ops_where(arity=2, result=TYP_BOOL):
        # pick x, y. compute result = x OP y. check result
        for vec in gen_vectors(fp_ops, 2, num_tests):
            x, y   = vec["values"]
            result = fp_eval_predicate(fp_ops, x, y)

            with new_test(vec) as fd:
                smt_write_header(fd, vec["expectation"])
                smt_write_vars(fd, vec)

                smt_write_var(fd, "result", "Bool",
                              "(= result (%s x y))" % smt_opsname(fp_ops))

                smt_write_goal(fd, "result", vec["expectation"], result)
                smt_write_footer(fd)

def mk_tests_for_binary(num_tests):
    for fp_ops in all_ops_where(arity=2, result=TYP_FLOAT):
        # pick x, y. compute result = x OP y. check result
        for vec in gen_vectors(fp_ops, 2, num_tests):
            x, y = vec["values"]
            try:
                result = fp_eval_function(fp_ops, vec["rounding"], x, y)
            except Unspecified:
                continue

            with new_test(vec) as fd:
                smt_write_header(fd, vec["expectation"])
                smt_write_vars(fd, vec)

                if is_rounding(fp_ops):
                    smt_write_var(fd, "result", result.smtlib_sort(),
                                  "(= result (%s %s x y))" %
                                  (smt_opsname(fp_ops), vec["rounding"]))
                else:
                    smt_write_var(fd, "result", result.smtlib_sort(),
                                  "(= result (%s x y))" % smt_opsname(fp_ops))
                smt_write_goal(fd,
                               "(= result %s)" %
                               result.smtlib_random_literal(),
                               vec["expectation"])
                smt_write_footer(fd)

def mk_tests_for_ternary(num_tests):
    fp_ops = "fp.fma"

    # pick x, y. compute result = x OP y. check result
    for vec in gen_vectors("fp.fma", 3, num_tests):
        x, y, z = vec["values"]
        result  = fp_eval_function(fp_ops, vec["rounding"], x, y, z)

        with new_test(vec) as fd:
            smt_write_header(fd, vec["expectation"])
            smt_write_vars(fd, vec)
            smt_write_var(fd, "result", result.smtlib_sort(),
                          "(= result (%s %s x y z))" % (smt_opsname(fp_ops),
                                                        vec["rounding"]))
            smt_write_goal(fd,
                           "(= result %s)" %
                           result.smtlib_random_literal(),
                           vec["expectation"])
            smt_write_footer(fd)

def mk_tests_conv_on_bitvector(num_tests):
    # convert signed and unsigned bitvector to float
    def mk_test_from(vec):
        assert vec["ops"] in ("fp.from.ubv", "fp.from.sbv")

        interval = random.choice(["<=", "=", ">="])

        x = vec["values"][0]

        fmt = random.choice([
            (5, 11),
            (8, 24),
            (11, 53),
            #(15, 113),
            #(random.randint(3, 10), random.randint(3, 10)),
        ])
        f = MPF(fmt[0], fmt[1])

        if vec["ops"] == "fp.from.ubv":
            as_int = x.to_unsigned_int()
            bv_rel = {"<=" : "bvule",
                      "="  : "=",
                      ">=" : "bvuge"}[interval]
            fp_ops = f.smtlib_from_ubv()
        else:
            assert vec["ops"] == "fp.from.sbv"
            as_int = x.to_signed_int()
            bv_rel = {"<=" : "bvsle",
                      "="  : "=",
                      ">=" : "bvsge"}[interval]
            fp_ops = f.smtlib_from_sbv()

        q = Rational(as_int)
        f.from_rational(vec["rounding"], q)

        with new_test(vec) as fd:
            smt_write_header(fd,
                             status  = vec["expectation"],
                             comment = vec["comment"],
                             logic   = "QF_FPBV")
            smt_write_var(
                fd,
                var_name    = "x",
                var_type    = x.smtlib_sort(),
                assertion   = "(%s x %s)" % (bv_rel,
                                             x.smtlib_random_literal()),
                expectation = str(as_int))
            smt_write_var(
                fd,
                var_name    = "r",
                var_type    = f.smtlib_sort(),
                assertion   = "(= r (%s %s x))" % (fp_ops,
                                                   vec["rounding"]))
            smt_write_goal(
                fd,
                bool_expr   = "(%s r %s)" % ({"<=" : "fp.leq",
                                              "="  : "fp.eq",
                                              ">=" : "fp.geq"}[interval],
                                             f.smtlib_random_literal()),
                expectation = vec["expectation"])
            smt_write_footer(fd)

    # convert float (+/- some interesting values) to a bitvector
    def mk_test_to(vec, bv_width, shift=Rational(0)):
        assert vec["ops"] in ("fp.to.ubv", "fp.to.sbv")

        x = vec["values"][0]
        if not shift.isZero():
            if x.isInfinite() or x.isNaN():
                return
            fudge = x.new_mpf()
            fudge.from_rational(vec["rounding"], shift)
            x = fp_add(RM_RNE, x, fudge) # RNE is used on purpose

        try:
            if vec["ops"] == "fp.to.ubv":
                bv = fp_to_ubv(x, vec["rounding"], bv_width)
                y_expectation = str(bv.to_unsigned_int())
            else:
                bv = fp_to_sbv(x, vec["rounding"], bv_width)
                y_expectation = str(bv.to_signed_int())
            unspecified = False
            expectation = vec["expectation"]
        except Unspecified:
            bv = BitVector(bv_width)
            for i in xrange(bv_width):
                bv.bv[i] = random.randint(0, 1)
            y_expectation = "unspecified"
            unspecified = True
            expectation = "sat"

        with new_test(vec) as fd:
            smt_write_header(fd, expectation, vec["comment"], "QF_FPBV")
            if unspecified:
                smt_write_comment(fd,
                                  "This benchmark relies on partial functions.")
            smt_write_var(
                fd,
                var_name    = "x",
                var_type    = x.smtlib_sort(),
                assertion   = "(= x %s)" % x.smtlib_random_literal(),
                expectation = str(x))
            smt_write_var(
                fd,
                var_name    = "y",
                var_type    = bv.smtlib_sort(),
                assertion   = "(= y ((_ %s %u) %s x))" % (
                    {"fp.to.ubv" : "fp.to_ubv",
                     "fp.to.sbv" : "fp.to_sbv"}[vec["ops"]],
                    bv.width,
                    vec["rounding"]),
                expectation = y_expectation)
            if not unspecified or random.randint(0, 1) == 0:
                z_assertion = "(= z %s)" % bv.smtlib_random_literal()
                z_expectation = {"fp.to.ubv" : bv.to_unsigned_int(),
                                 "fp.to.sbv" : bv.to_signed_int()}[vec["ops"]]
            else:
                z_assertion = None
                z_expectation = None
            smt_write_var(
                fd,
                var_name    = "z",
                var_type    = bv.smtlib_sort(),
                assertion   = z_assertion,
                expectation = z_expectation)
            smt_write_goal(
                fd,
                bool_expr   = "(= y z)",
                expectation = expectation,
                correct_answer = (random.choice([True, False])
                                  if unspecified
                                  else True))
            smt_write_footer(fd)

    ######################################################################
    # signed or unsigned --> float
    ######################################################################

    for vec in gen_bv_vectors("fp.from.ubv", 1, num_tests):
        mk_test_from(vec)

    for vec in gen_bv_vectors("fp.from.sbv", 1, num_tests):
        mk_test_from(vec)

    ######################################################################
    # float --> signed or unsigned
    ######################################################################

    q_half = Rational(1, 2)
    for vec in gen_vectors("fp.to.ubv", 1, num_tests):
        for bv_width in (8, 32, 64):
            mk_test_to(vec, bv_width)
            mk_test_to(vec, bv_width, shift=q_half)
            mk_test_to(vec, bv_width, shift=-q_half)

    for vec in gen_vectors("fp.to.sbv", 1, num_tests):
        for bv_width in (8, 32, 64):
            mk_test_to(vec, bv_width)
            mk_test_to(vec, bv_width, shift=q_half)
            mk_test_to(vec, bv_width, shift=-q_half)

    ######################################################################
    # binary interchange --> float
    ######################################################################

    for vec in gen_vectors("fp.from.binary", 1, num_tests):
        # We do the conversion both ways. First bitvector to float...
        with new_test(vec) as fd:
            y = vec["values"][0]
            x = BitVector(y.k)
            x.from_unsigned_int(y.bv)

            smt_write_header(fd, vec["expectation"], vec["comment"], "QF_FPBV")
            smt_write_comment(fd, "binary interchange -> float")
            smt_write_var(fd, "x", x.smtlib_sort(),
                          "(= x %s)" % x.smtlib_random_literal(),
                          "%x" % x.to_unsigned_int())
            smt_write_var(fd, "y", y.smtlib_sort(),
                          "(= y (%s x))" % y.smtlib_from_binary_interchange(),
                          str(y))
            smt_write_goal(fd, "(= y %s)" % y.smtlib_literal(),
                           vec["expectation"])
            smt_write_footer(fd)

        # Then from float to bitvector (we just need to be careful
        # with the unspecified cast at NaN).
        with new_test(vec) as fd:
            x = vec["values"][0]
            y = BitVector(x.k)
            y.from_unsigned_int(x.bv)

            unspecified = x.isNaN()
            expectation = "sat" if unspecified else vec["expectation"]

            smt_write_header(fd, expectation, vec["comment"], "QF_FPBV")
            smt_write_comment(fd, "float -> binary interchange")
            if unspecified:
                smt_write_comment(fd,
                                  "this test relies on unspecified functions")
            smt_write_vars(fd, vec)

            smt_write_var(fd, "y", y.smtlib_sort(),
                          "(= (%s y) x)" % x.smtlib_from_binary_interchange(),
                          y.smtlib_literal())
            smt_write_goal(fd, "(= y %s)" % y.smtlib_literal(), expectation)
            smt_write_footer(fd)


def mk_tests_conv_on_real(num_tests):
    # We pick a random float; then determine the rational interval that would
    # round onto that float. we then select rationals from:
    #   - outisde that interval,
    #   - inside the interval,
    #   - just on the boundary
    # We then apply ((_ to_fp eb sb) rm RATIONAL) and make sure we get the
    # correct result.

    for vec in gen_vectors("fp.from.real", 1, num_tests):
        x = vec["values"][0]
        if x.isNaN():
            # This can't happen, so lets skip these
            continue

        interval = fp_interval(vec["rounding"], x)
        if interval is None:
            assert vec["rounding"] in MPF.ROUNDING_MODES_DIRECTED
            # It is not possible to construct an interval in some cases
            continue

        def emit_test(q, result, expectation, comment):
            tmp = x.new_mpf()
            tmp.from_rational(vec["rounding"], q)
            #print x, q, result, expectation, comment
            #assert smtlib_eq(tmp, x) == result

            with new_test(vec) as fd:
                smt_write_header(fd, expectation, comment)
                smt_write_vars(fd, vec)
                smt_write_var(fd, "w", x.smtlib_sort(),
                              "(= w (%s %s %s))" % (x.smtlib_from_real(),
                                                    vec["rounding"],
                                                    q.to_smtlib()),
                              str(tmp))
                smt_write_goal(fd,
                               "(%s x w)" % ("="
                                             if result
                                             else "distinct"),
                               expectation)
                smt_write_footer(fd)

        def invert_expectation(expectation):
            if expectation == "unsat":
                return "sat"
            else:
                return "unsat"

        def check_interval_bound(bound, comment):
            if bound.kind == KIND_INCLUSIVE:
                emit_test(bound.value,
                          True,
                          vec["expectation"],
                          comment + " (inclusive)")
            elif bound.kind == KIND_EXCLUSIVE:
                emit_test(bound.value,
                          False,
                          invert_expectation(vec["expectation"]),
                          comment + " (exclusive)")

        # we pick a value somewhere inside the interval
        emit_test(random_rational(interval.low, interval.high),
                  True,
                  vec["expectation"],
                  "inside interval")

        # we then check the upper and lower bound
        check_interval_bound(interval.low, "on low bound")
        check_interval_bound(interval.high, "on high bound")

        # we also pick values outside the interval
        if interval.low.kind != KIND_INFINITE:
            l = Interval_Bound(KIND_INFINITE)
            h = Interval_Bound(KIND_EXCLUSIVE, interval.low.value)
            emit_test(random_rational(l, h), False, vec["expectation"], "below")
        if interval.high.kind != KIND_INFINITE:
            l = Interval_Bound(KIND_EXCLUSIVE, interval.high.value)
            h = Interval_Bound(KIND_INFINITE)
            emit_test(random_rational(l, h), False, vec["expectation"], "above")

        # Finally, we emit a test from a non-literal real to float. We
        # do this by creating a real variable, asserting it lies in
        # the interval we've worked out using < and <=, and converting
        # to float.
        with new_test(vec) as fd:
            smt_write_header(fd, vec["expectation"],
                             comment = "hard: non-literal interval check",
                             logic   = "QF_FPLRA")
            smt_write_vars(fd, vec)
            bounds = []
            if interval.low.kind == KIND_INCLUSIVE:
                bounds.append("(>= r %s)" % interval.low.value.to_smtlib())
            elif interval.low.kind == KIND_EXCLUSIVE:
                bounds.append("(> r %s)" % interval.low.value.to_smtlib())
            if interval.high.kind == KIND_INCLUSIVE:
                bounds.append("(<= r %s)" % interval.high.value.to_smtlib())
            elif interval.high.kind == KIND_EXCLUSIVE:
                bounds.append("(< r %s)" % interval.high.value.to_smtlib())
            if len(bounds) == 0:
                bounds_assertion = None
            elif len(bounds) == 1:
                bounds_assertion = bounds[0]
            else:
                bounds_assertion = "(and %s)" % " ".join(bounds)
            smt_write_var(fd,
                          var_name = "r",
                          var_type = "Real",
                          assertion = bounds_assertion)

            smt_write_var(fd, "w", x.smtlib_sort(),
                          "(= w (%s %s r))" % (x.smtlib_from_real(),
                                               vec["rounding"]))
            smt_write_goal(fd,
                           "(= x w)",
                           vec["expectation"])
            smt_write_footer(fd)

    # For the float to real tests we can a bunch of things.
    #
    # First we pick a random float based on our usual selection
    # criteria. Then:
    #
    # (1) Assert float, and convert to real. Check expecation. If the
    #     float is NaN or Inf then the problem is always SAT.
    #
    # (2) Pick a real based on the float. Either its precise value, or
    #     (50% of the time) something close. Assert the real and
    #     assert the float converts to it. Sometimes assert the float
    #     is finite to rule out the obvious sat stuff for INF and NaN.
    for vec in gen_vectors("fp.to.real", 1, num_tests):
        x = vec["values"][0]

        # (1)

        unspecified = x.isNaN() or x.isInfinite()
        if unspecified:
            expectation = "sat"
            logic       = "QF_UFFPLRA"
            q           = Rational(random.randint(-2**64, 2**64),
                                   random.randint(1, 2**32))
        else:
            expectation = vec["expectation"]
            logic       = "QF_FPLRA"
            q           = x.to_rational()

        with new_test(vec) as fd:
            smt_write_header(fd, expectation, logic=logic)
            smt_write_vars(fd, vec)

            if unspecified:
                smt_write_comment(fd, "this relies on unspecified behaviour")
            smt_write_var(fd,
                          var_name    = "y",
                          var_type    = "Real",
                          assertion   = "(= y (%s x))" % x.smtlib_to_real(),
                          expectation = str(q))

            smt_write_goal(fd,
                           bool_expr   = "(= y %s)" % q.to_smtlib(),
                           expectation = expectation)

            smt_write_footer(fd)

        # (2)

        interval_unspecified = x.isNaN() or x.isInfinite()
        if interval_unspecified:
            logic              = "QF_UFFPLRA"
            is_sat             = True
            assert_x_is_finite = False
            assert_x_distinct  = False
            q = Rational(random.randint(-2**64, 2**64),
                         random.randint(1, 2**32))
            comment_z = "a random rational"
        else:
            is_sat = vec["expectation"] == "sat"
            is_rep = random.choice([False, True])
            if is_sat:
                # To make it sat, we have have two choices: a) make the
                # real representable, or b) make sure that we do not make
                # x finite.
                if is_rep:
                    logic              = "QF_FPLRA"
                    assert_x_is_finite = random.choice([False, True])
                else:
                    logic              = "QF_UFFPLRA"
                    assert_x_is_finite = False
                assert_x_distinct  = False
            else:
                # To make it unsat we definitely need to make x
                # finite. We can then either pick a non-rep real, or
                # we can assert its a distinct from the correct
                # answer.
                logic              = "QF_FPLRA"
                assert_x_is_finite = True
                assert_x_distinct  = is_rep

            if is_rep:
                q = x.to_rational()
                comment_z = "a representable real"
            else:
                interval = fp_interval(RM_RNA, x)
                while True:
                    q = random_rational(interval.low, interval.high)
                    if q != x.to_rational():
                        break
                comment_z = "a non-representable real"

        if is_sat:
            expectation = "sat"
        else:
            expectation = "unsat"

        with new_test(vec) as fd:
            smt_write_header(fd, expectation, logic=logic)
            smt_write_var(fd,
                          var_name = "x",
                          var_type = x.smtlib_sort())
            if assert_x_is_finite:
                smt_write_assertion(fd,
                                    "(or (fp.isZero x) (fp.isSubnormal x) (fp.isNormal x))")
            if assert_x_distinct:
                smt_write_assertion(fd, "(distinct x %s)" % x.smtlib_random_literal())

            smt_write_var(fd,
                          var_name = "y",
                          var_type = "Real",
                          assertion = "(= y (%s x))" % x.smtlib_to_real())

            smt_write_var(fd,
                          var_name = "z",
                          var_type = "Real",
                          assertion = "(= z %s)" % q.to_smtlib(),
                          expectation = comment_z)

            smt_write_goal(fd, "(= y z)", "sat") # The sat answer is fudged
            smt_write_footer(fd)


def mk_tests_conv_on_int(num_tests):
    ######################################################################
    # int -> float tests
    #
    # Currently:
    # - we pick a random integer and convert it to float
    #
    # Todo:
    # - pick two integers and say something about the interval
    ######################################################################

    def int_to_smtlib(n):
        if n < 0:
            return "(- %u)" % (- n)
        else:
            return "%u" % n

    for vec in gen_int_vectors("fp.from.int", 1, num_tests):
        f = MPF(*vec["mpf_fmt"])
        f.from_rational(vec["rounding"], Rational(vec["values"]))

        with new_test(vec) as fd:
            smt_write_header(fd,
                             vec["expectation"], vec["comment"],
                             logic="QF_FPLIA")
            smt_write_var(fd,
                          var_name  = "x",
                          var_type  = "Int",
                          assertion = "(= x %s)" % int_to_smtlib(vec["values"]))
            smt_write_var(fd,
                          var_name    = "y",
                          var_type    = f.smtlib_sort(),
                          assertion   = "(= y (%s x))" % f.smtlib_from_int(),
                          expectation = str(f))
            smt_write_var(fd,
                          var_name   = "z",
                          var_type   = f.smtlib_sort(),
                          assertion  = "(= z %s)" % f.smtlib_random_literal())
            smt_write_goal(fd, "(= y z)", vec["expectation"])

    ######################################################################
    # float -> int tests
    #
    # Currently:
    # - we pick a random float and convert it to int
    ######################################################################

    for vec in gen_vectors("fp.to.int", 1, num_tests):
        x = vec["values"][0]

        if x.isFinite():
            n           = fp_to_int(vec["rounding"], x)
            expectation = vec["expectation"]
            ex_y        = "%i" % n
            logic       = "QF_FPLIA"
        else:
            n           = random.randint(-2 * x.inf_boundary(),
                                         x.inf_boundary())
            expectation = "sat"
            ex_y        = "unspecified"
            logic       = "QF_UFFPLIA"

        with new_test(vec) as fd:
            smt_write_header(fd,
                             expectation, vec["comment"], logic)
            smt_write_vars(fd, vec)
            smt_write_var(fd,
                          var_name    = "y",
                          var_type    = "Int",
                          assertion   = "(= y (%s x))" % x.smtlib_to_int(),
                          expectation = ex_y)
            smt_write_var(fd,
                          var_name  = "z",
                          var_type  = "Int",
                          assertion = "(= z %s)" % int_to_smtlib(n))
            smt_write_goal(fd, "(= y z)", vec["expectation"])


def mk_tests_conv_on_float(num_tests):
    # We pick a random float; then a bunch of target precisions
    # (smaller and larger) and convert.
    PRECISIONS = [(5, 11),
                  (8, 24),
                  (11, 53),
                  (15, 113)]

    for vec in gen_vectors("fp.cast", 1, num_tests):
        src = vec["values"][0]
        for target_eb, target_sb in PRECISIONS:
            dst = fp_from_float(target_eb, target_sb, vec["rounding"], src)
            if src.compatible(dst):
                # Skip trivial casts
                continue

            vec["comment"] = ("%s conversion of %s(%s) -> %s" %
                              (vec["rounding"],
                               src.smtlib_sort(),
                               vec["raw_kinds"][0],
                               dst.smtlib_sort()))

            with new_test(vec) as fd:
                smt_write_header(fd, vec["expectation"], vec["comment"])

                smt_write_vars(fd, vec)
                smt_write_var(fd, "y",
                              var_type  = dst.smtlib_sort(),
                              assertion = ("(= y (%s %s %s))" %
                                           (dst.smtlib_from_float(),
                                            vec["rounding"],
                                            "x")),
                              expectation = str(dst))
                smt_write_var(fd, "z",
                              var_type = dst.smtlib_sort(),
                              assertion = "(= z %s)" % dst.smtlib_random_literal(),
                              expectation = "y")
                smt_write_goal(fd, "(= y z)", vec["expectation"])
                smt_write_footer(fd)

def main():
    ap = argparse.ArgumentParser(
        description="Generate random SMTLIB testcases.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--test_classify", metavar="N", type=int,
                    default=0,
                    help="Generate tests for the classification operators.")
    ap.add_argument("--test_unary", metavar="N", type=int,
                    default=0,
                    help="Generate tests for all unary operators.")
    ap.add_argument("--test_binary", metavar="N", type=int,
                    default=0,
                    help="Generate tests for all binary operators.")
    ap.add_argument("--test_ternary", metavar="N", type=int,
                    default=0,
                    help="Generate tests for all ternary operators.")
    ap.add_argument("--test_relations", metavar="N", type=int,
                    default=0,
                    help="Generate tests for all binary relations.")
    ap.add_argument("--test_conversion", metavar="N", type=int,
                    default=0,
                    help="Generate tests for conversion to/from float.")
    options = ap.parse_args()

    for d in glob("fp.*") + glob("smtlib.*"):
        if os.path.isdir(d):
            shutil.rmtree(d)
    for f in glob("eval__*"):
        os.unlink(f)

    if options.test_classify >= 1:
        mk_tests_for_classify(options.test_classify)
    if options.test_relations >= 1:
        mk_tests_for_relations(options.test_relations)
    if options.test_unary >= 1:
        mk_tests_for_unary(options.test_unary)
    if options.test_binary >= 1:
        mk_tests_for_binary(options.test_binary)
    if options.test_ternary >= 1:
        mk_tests_for_ternary(options.test_ternary)
    if options.test_conversion >= 1:
        mk_tests_conv_on_bitvector(options.test_conversion)
        mk_tests_conv_on_real(options.test_conversion)
        mk_tests_conv_on_float(options.test_conversion)
        mk_tests_conv_on_int(options.test_conversion)

if __name__ == "__main__":
    main()
