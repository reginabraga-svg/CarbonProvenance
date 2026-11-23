"""Contracts as SHACL shapes over the PROV-O export, checked with pySHACL and compared with the ledger.

S1 (violation) a sum or difference whose inputs differ in quantity kind or unit
S2 (warning)   a value on one spatial support produced by copying a value of another support
S3 (violation) a derived value with an ancestor that has no primary source (missing or withdrawn input)
"""
import time

from pyshacl import validate
from rdflib import Graph

SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix prov: <http://www.w3.org/ns/prov#> .
@prefix gov: <https://example.org/govprov#> . @prefix ex: <https://example.org/shapes/> .

ex:S1 a sh:NodeShape ; sh:targetSubjectsOf prov:wasGeneratedBy ; sh:severity sh:Violation ;
  sh:sparql [ sh:message "additive operation over inputs of different quantity kind or unit" ;
    sh:prefixes ex:p ;
    sh:select \"\"\"SELECT $this WHERE { $this prov:wasGeneratedBy ?a . ?a gov:operation ?op . FILTER(?op IN ("sum","diff"))
       ?a prov:used ?x, ?y . ?x gov:quantityKind ?kx ; gov:unit ?ux . ?y gov:quantityKind ?ky ; gov:unit ?uy .
       FILTER(?kx != ?ky || ?ux != ?uy) }\"\"\" ] .

ex:S2 a sh:NodeShape ; sh:targetSubjectsOf prov:wasGeneratedBy ; sh:severity sh:Warning ;
  sh:sparql [ sh:message "value copied from another spatial support" ; sh:prefixes ex:p ;
    sh:select \"\"\"SELECT $this WHERE { $this prov:wasGeneratedBy ?a ; gov:support ?s . ?a gov:operation "broadcast" ;
       prov:used ?x . ?x gov:support ?sx . FILTER(?s != ?sx) }\"\"\" ] .

ex:S3 a sh:NodeShape ; sh:targetSubjectsOf prov:wasGeneratedBy ; sh:severity sh:Violation ;
  sh:sparql [ sh:message "lineage does not reach a primary source" ; sh:prefixes ex:p ;
    sh:select \"\"\"SELECT $this WHERE { $this prov:wasDerivedFrom* ?x . ?x prov:wasDerivedFrom ?y .
       FILTER NOT EXISTS { ?y prov:hadPrimarySource ?src } FILTER NOT EXISTS { ?y prov:wasGeneratedBy ?act } }\"\"\" ] .

ex:p sh:declare [ sh:prefix "prov" ; sh:namespace "http://www.w3.org/ns/prov#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                [ sh:prefix "gov" ; sh:namespace "https://example.org/govprov#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] .
"""


def check(g: Graph):
    t0 = time.perf_counter()
    conforms, rg, _ = validate(g, shacl_graph=Graph().parse(data=SHAPES, format="turtle"), advanced=True)
    q = """PREFIX sh: <http://www.w3.org/ns/shacl#> SELECT ?f ?shape ?sev WHERE { ?r sh:focusNode ?f ; sh:sourceShape ?shape ; sh:resultSeverity ?sev }"""
    res = [(str(f), str(s).split("/")[-1], str(v).split("#")[-1]) for f, s, v in rg.query(q)]
    return res, time.perf_counter() - t0
