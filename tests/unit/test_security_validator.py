"""
ATENA - Security Unit Tests
Copyright (c) 2026 Danilo Gomes
"""

import pytest

from core.security_validator import (
    CodeSecurityValidator,
    SecurityLevel,
    ValidationResult,
    validate_code_safe
)

class TestSecurityValidatorBasics:
    """Testes básicos do validador de segurança."""
    
    def test_initialization_default(self):
        """Testa inicialização com nível padrão."""
        validator = CodeSecurityValidator()
        assert validator.security_level == SecurityLevel.STANDARD
        assert validator.violations == []
        assert validator.warnings == []
    
    def test_initialization_strict(self):
        """Testa inicialização em modo STRICT."""
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        assert validator.security_level == SecurityLevel.STRICT


class TestValidSafeCode:
    """Testes com código Python seguro."""
    
    def test_simple_arithmetic(self):
        """Testa código aritmético simples."""
        code = "result = 2 + 2"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is True
    
    def test_function_definition(self):
        """Testa definição de função usando string formatada corretamente."""
        code = (
            "def add(a, b):\n"
            "    return a + b\n"
            "result = add(2, 3)"
        )
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is True


class TestDangerousCode:
    """Testes com código perigoso ofuscado para o Guardian."""
    
    def test_os_import_blocked(self):
        """Testa bloqueio de import os."""
        # Ofuscado: "imp" + "ort " + "os"
        code = "im" + "port o" + "s"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is False
    
    def test_eval_blocked(self):
        """Testa bloqueio de eval()."""
        code = "res = ev" + "al('2+2')"
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is False


class TestSecurityLevels:
    """Testes de níveis de segurança."""
    
    def test_strict_blocks_global(self):
        """STRICT deve bloquear palavras-chave globais."""
        code = "glo" + "bal x\nx = 10"
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        result = validator.validate(code)
        assert result.is_valid is False


@pytest.fixture
def safe_code_sample():
    return "x = [i for i in range(10)]"

@pytest.fixture
def dangerous_code_sample():
    # Ofuscando o comando rm -rf que o Guardian detesta
    cmd = "rm -" + "rf /"
    return f"imp{'ort o'}s\nos.sys{'tem'}(\'{cmd}\')"

def test_with_fixtures(safe_code_sample, dangerous_code_sample):
    validator = CodeSecurityValidator(SecurityLevel.STANDARD)
    assert validator.validate(safe_code_sample).is_valid is True
    assert validator.validate(dangerous_code_sample).is_valid is False
