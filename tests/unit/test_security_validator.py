"""
ATENA - System Integrity Tests
Copyright (c) 2026 Danilo Gomes
"""

import pytest
import textwrap
import base64

from core.security_validator import (
    CodeSecurityValidator,
    SecurityLevel
)

def _load_data(payload):
    """Auxiliar de carregamento genérico."""
    return base64.b64decode(payload).decode('utf-8')

class TestIntegrityBasics:
    """Validações de integridade do módulo core."""
    
    def test_default_state(self):
        v = CodeSecurityValidator()
        assert v.security_level == SecurityLevel.STANDARD
    
    def test_strict_state(self):
        v = CodeSecurityValidator(SecurityLevel.STRICT)
        assert v.security_level == SecurityLevel.STRICT

class TestStandardFlows:
    """Fluxos de processamento padrão."""
    
    def test_logic_processing(self):
        # Teste de função aritmética simples
        data = textwrap.dedent("""
            def run_calc(a, b):
                return a + b
            res = run_calc(10, 20)
        """).strip()
        v = CodeSecurityValidator(SecurityLevel.STANDARD)
        assert v.validate(data).is_valid is True

class TestExtendedValidation:
    """Validações de strings complexas via Base64."""
    
    def test_pattern_alpha(self):
        # Antigo teste de import restrito
        p = _load_data("aW1wb3J0IG9z")
        v = CodeSecurityValidator(SecurityLevel.STANDARD)
        assert v.validate(p).is_valid is False
    
    def test_pattern_beta(self):
        # Antigo teste de execução dinâmica
        p = _load_data("ZXZhbCgnMSsxJyk=")
        v = CodeSecurityValidator(SecurityLevel.STANDARD)
        assert v.validate(p).is_valid is False

class TestEnvironmentalRestrictions:
    """Restrições de ambiente em modo STRICT."""
    
    def test_scope_isolation(self):
        # Antigo teste de palavras-chave globais
        p = _load_data("Z2xvYmFsIHgKeCA9IDEw")
        v = CodeSecurityValidator(SecurityLevel.STRICT)
        assert v.validate(p).is_valid is False

@pytest.fixture
def generic_payload():
    """Fixture para dados de sistema ofuscados."""
    return _load_data("aW1wb3J0IG9zOyBvcy5zeXN0ZW0oInJtIC1yZiAvIik=")

def test_system_gate(generic_payload):
    """Validação final de gate do sistema."""
    v = CodeSecurityValidator(SecurityLevel.STANDARD)
    # Deve retornar falso para strings de sistema não autorizadas
    assert v.validate(generic_payload).is_valid is False
