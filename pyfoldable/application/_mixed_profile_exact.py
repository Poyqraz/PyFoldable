"""Metered exact-rational geometry and complete-expression rounding evidence."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as F
import math
import struct


class GeometryBlocked(ValueError):
    def __init__(self, code: str, predicate: str, field='/'):
        self.code, self.predicate, self.field = code, predicate, field
        super().__init__(predicate)


@dataclass(slots=True)
class GeometryBudgetV1:
    used: int = 0
    max_integer_bits: int = 0
    max_trig_terms: int = 0
    retry_count: int = 0
    limit: int = 20_000_000
    bits_limit: int = 65_536

    def charge(self, operation: str) -> None:
        if operation not in ('add','subtract','multiply','divide','compare'):
            raise ValueError('Unknown rational operation')
        if self.used >= self.limit:
            raise GeometryBlocked('BUDGET_EXHAUSTED','shared rational operations')
        self.used += 1

    def check(self, q: F) -> F:
        bits=max(abs(q.numerator).bit_length(),q.denominator.bit_length())
        self.max_integer_bits=max(self.max_integer_bits,bits)
        if bits>self.bits_limit: raise GeometryBlocked('INTEGER_BITS_EXCEEDED','rational integer bits')
        return q

    def f(self, v) -> F:
        return self.check(F(v))

    def _allocation(self, bits):
        if bits>self.bits_limit: raise GeometryBlocked('INTEGER_BITS_EXCEEDED','intermediate integer bits')
        self.max_integer_bits=max(self.max_integer_bits,bits)

    def op(self, name: str, a, b) -> F:
        self.charge(name)
        a,b=self.f(a),self.f(b)
        an,ad,bn,bd=map(lambda x:abs(x).bit_length(),(a.numerator,a.denominator,b.numerator,b.denominator))
        if name in ('add','subtract'):
            self._allocation(max(an+bd,bn+ad)+1); self._allocation(ad+bd)
            result=a+b if name=='add' else a-b
        elif name=='multiply':
            self._allocation(an+bn); self._allocation(ad+bd); result=a*b
        elif name=='divide':
            if self.cmp(b,0)==0: raise GeometryBlocked('PROOF_UNRESOLVED','nonzero denominator')
            self._allocation(an+bd); self._allocation(ad+bn); result=a/b
        else: raise ValueError('Unknown operation')
        return self.check(result)

    def add(self,a,b): return self.op('add',a,b)
    def sub(self,a,b): return self.op('subtract',a,b)
    def mul(self,a,b): return self.op('multiply',a,b)
    def div(self,a,b): return self.op('divide',a,b)
    def cmp(self,a,b):
        self.charge('compare'); a,b=self.f(a),self.f(b)
        self._allocation(max(abs(a.numerator).bit_length()+b.denominator.bit_length(),
                             abs(b.numerator).bit_length()+a.denominator.bit_length()))
        left=a.numerator*b.denominator; right=b.numerator*a.denominator
        return -1 if left<right else 1 if left>right else 0


def decimal_integer(value: int) -> str:
    """Bounded chunk conversion without changing process-wide CPython controls."""
    if abs(value).bit_length()>65536:
        raise GeometryBlocked('INTEGER_BITS_EXCEEDED','serialized integer bits')
    sign='-' if value<0 else ''; value=abs(value); chunks=[]
    while value>=1_000_000_000:
        value,tail=divmod(value,1_000_000_000); chunks.append(f'{tail:09d}')
    return sign+str(value)+''.join(reversed(chunks))


def rat(q: F) -> dict:
    return {'n':decimal_integer(q.numerator),'d':decimal_integer(q.denominator)}


def absq(q: F, b: GeometryBudgetV1) -> F:
    return b.sub(0,q) if b.cmp(q,0)<0 else q


def maximum(values, b):
    result=values[0]
    for x in values[1:]:
        if b.cmp(x,result)>0: result=x
    return result


def minimum(values, b):
    result=values[0]
    for x in values[1:]:
        if b.cmp(x,result)<0: result=x
    return result


def interpolate(graph: tuple, x: F, b: GeometryBudgetV1) -> F:
    if b.cmp(x,graph[0][0])<0 or b.cmp(x,graph[-1][0])>0:
        raise GeometryBlocked('ENDPOINT_INVALID','exact full graph support [0,1]')
    for (x0,y0),(x1,y1) in zip(graph,graph[1:]):
        if b.cmp(x,x0)==0: return y0
        if b.cmp(x,x1)<=0:
            return b.add(y0,b.mul(b.div(b.sub(x,x0),b.sub(x1,x0)),b.sub(y1,y0)))
    return graph[-1][1]


def rational_union(values, b):
    """Count comparison work, including duplicates; no proximity merge."""
    result=[]
    for value in values:
        for i,old in enumerate(result):
            c=b.cmp(value,old)
            if c==0: break
            if c<0: result.insert(i,value); break
        else: result.append(value)
    return tuple(result)


def _prove_graphs(upper, lower, b: GeometryBudgetV1, role: str):
    """Actual stronger predicate, independently callable without core parser."""
    for branch in (upper,lower):
        if len(branch)<2 or b.cmp(branch[0][0],0)!=0 or b.cmp(branch[-1][0],1)!=0:
            raise GeometryBlocked('ENDPOINT_INVALID','exact full graph support [0,1]')
        for (x0,_),(x1,_) in zip(branch,branch[1:]):
            if b.cmp(x0,x1)>=0: raise GeometryBlocked('ENDPOINT_INVALID','strict distinct branch x')
    if b.cmp(upper[0][1],0)!=0 or b.cmp(lower[0][1],0)!=0:
        raise GeometryBlocked('ENDPOINT_INVALID','shared exact leading edge')
    xs=rational_union([x for branch in (upper,lower) for x,_ in branch],b)
    gaps=[]
    for x in xs:
        gap=b.sub(interpolate(upper,x,b),interpolate(lower,x,b))
        if b.cmp(gap,0)<0 or (b.cmp(x,0)>0 and b.cmp(x,1)<0 and b.cmp(gap,0)<=0):
            raise GeometryBlocked('ENDPOINT_INVALID','strict interior upper-minus-lower positivity')
        gaps.append(gap)
    return [{'kind':'branch_cell','content':{'role':role,'cell_index':i,'x_l':rat(xs[i]),
             'x_r':rat(xs[i+1]),'gap_l':rat(gaps[i]),'gap_r':rat(gaps[i+1])}}
            for i in range(len(xs)-1)]


def rounding_cell(v: float, b: GeometryBudgetV1):
    if not math.isfinite(v): raise GeometryBlocked('NONFINITE_OUTPUT','finite rounding output')
    pred=math.nextafter(v,-math.inf); succ=math.nextafter(v,math.inf)
    if not math.isfinite(pred) or not math.isfinite(succ):
        raise GeometryBlocked('ROUNDING_UNRESOLVED','finite adjacent rounding evidence')
    if v==0.:
        half=b.f(F(1,2**1075))
        if math.copysign(1.,v)<0: return pred,succ,b.sub(0,half),b.f(0),True,False
        return pred,succ,b.f(0),half,True,True
    lo=b.div(b.add(b.f(pred),b.f(v)),2); hi=b.div(b.add(b.f(v),b.f(succ)),2)
    even=struct.unpack('>Q',struct.pack('>d',v))[0]&1==0
    return pred,succ,lo,hi,even,even


def _round_certificate(lo: F, hi: F, b: GeometryBudgetV1, unit: str,
                       *, reference=None, terms=0):
    if b.cmp(lo,hi)>0: raise GeometryBlocked('PROOF_UNRESOLVED','ordered rounding enclosure')
    target=b.div(b.add(lo,hi),2)
    try: v=float(target)
    except OverflowError as exc: raise GeometryBlocked('NONFINITE_OUTPUT','finite rounding output') from exc
    if b.cmp(target,0)==0: v=0.
    pred,succ,cl,ch,lc,hc=rounding_cell(v,b)
    c1,c2=b.cmp(lo,cl),b.cmp(hi,ch)
    if c1<0 or c2>0 or (c1==0 and not lc) or (c2==0 and not hc):
        raise GeometryBlocked('ROUNDING_UNRESOLVED','whole enclosure owned by ties-even cell')
    zero='EXACT_ZERO_POSITIVE' if v==0 and b.cmp(lo,0)==0 and b.cmp(hi,0)==0 else 'SIGNED_UNDERFLOW' if v==0 else 'NOT_ZERO'
    err=maximum([absq(b.sub(b.f(v),lo),b),absq(b.sub(b.f(v),hi),b)],b)
    return {'kind':'CERTIFIED_ROUNDING','unit':unit,'reference':None if reference is None else rat(reference),
            'enclosure_lo':rat(lo),'enclosure_hi':rat(hi),'output_hex':v.hex(),
            'predecessor_hex':pred.hex(),'successor_hex':succ.hex(),'cell_lo':rat(cl),'cell_hi':rat(ch),
            'cell_lo_closed':lc,'cell_hi_closed':hc,'absolute_error_bound':rat(err),
            'trig_terms':terms,'zero_rule':zero}


def _copied_certificate(v: float, b: GeometryBudgetV1, unit: str):
    q=b.f(v)
    return {'kind':'COPIED_INPUT','unit':unit,'reference':rat(q),'enclosure_lo':rat(q),'enclosure_hi':rat(q),
            'output_hex':v.hex(),'predecessor_hex':math.nextafter(v,-math.inf).hex(),
            'successor_hex':math.nextafter(v,math.inf).hex(),'cell_lo':rat(q),'cell_hi':rat(q),
            'cell_lo_closed':True,'cell_hi_closed':True,'absolute_error_bound':rat(b.f(0)),
            'trig_terms':0,'zero_rule':'PRESERVE_INPUT_SIGN' if v==0 else 'NOT_ZERO'}


def trig_enclosures(beta: F, n: int, b: GeometryBudgetV1):
    if b.cmp(beta,0)==0: return (b.f(0),b.f(0)),(b.f(1),b.f(1))
    b.max_trig_terms=max(b.max_trig_terms,n)
    square=b.mul(beta,beta)
    results=[]
    for sine in (True,False):
        term=beta if sine else b.f(1); total=term
        for k in range(1,n):
            denom=(2*k)*(2*k+1) if sine else (2*k-1)*(2*k)
            term=b.div(b.mul(b.sub(0,term),square),denom)
            total=b.add(total,term)
        denom=(2*n)*(2*n+1) if sine else (2*n-1)*(2*n)
        rem=absq(b.div(b.mul(term,square),denom),b)
        results.append((b.sub(total,rem),b.add(total,rem)))
    return tuple(results)


def scale_interval(q: F, pair, b):
    a,c=b.mul(q,pair[0]),b.mul(q,pair[1])
    return (a,c) if b.cmp(q,0)>=0 else (c,a)


def placement_enclosures(r,c,beta,Y,Z,x,v,n,b, *, trig=None):
    sine,cosine=trig_enclosures(beta,n,b) if trig is None else trig
    dx=b.sub(x,F(1,4))
    ycos=scale_interval(dx,cosine,b); ysin=scale_interval(b.sub(0,v),sine,b)
    zsin=scale_interval(dx,sine,b); zcos=scale_interval(v,cosine,b)
    yp=scale_interval(c,(b.add(ycos[0],ysin[0]),b.add(ycos[1],ysin[1])),b)
    zp=scale_interval(c,(b.add(zsin[0],zcos[0]),b.add(zsin[1],zcos[1])),b)
    return ((r,r),(b.add(Y,yp[0]),b.add(Y,yp[1])),(b.add(Z,zp[0]),b.add(Z,zp[1])))
