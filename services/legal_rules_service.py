from __future__ import annotations
from dataclasses import dataclass

@dataclass
class LegalRule:
    key: str; source: str; value: float; unit: str; precedence: int = 100; is_hard: bool = False

class LegalRulesService:
    def __init__(self): self.rules = {}
    def register_rule(self, rule):
        self.rules.setdefault(rule.key,[]).append(rule)
    def resolve(self, key):
        candidates = self.rules.get(key,[])
        return sorted(candidates,key=lambda r:r.precedence)[0] if candidates else None
    def load_default_rules(self):
        self.register_rule(LegalRule("vacaciones_dias","estatuto_art_38_1",30,"dias",20))
        self.register_rule(LegalRule("vacaciones_dias","convenio_art_57",31,"dias",10))
        self.register_rule(LegalRule("descanso_entre_jornadas","estatuto_art_34_3",12,"horas",5,True))
