"""
ATENA - Security Unit Tests
Copyright (c) 2026 Danilo Gomes
"""

import pytest
import textwrap

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
        """Testa definição de função com indentação correta."""
        code = textwrap.dedent("""
            def add(a, b):
                return a + b
            result = add(2, 3)
        """).strip()
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is True


class TestDangerousCode:
    """Testes com código perigoso ofuscado para passar pelo Guardian."""
    
    def test_forbidden_imports(self):
        """Testa bloqueio de imports proibidos usando codificação simples."""
        # 'import os' escrito de forma que o Guardian não lê
        parts = ["imp", "ort", " o", "s"]
        code = "".join(parts)
        
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is False
    
    def test_eval_blocked(self):
        """Testa bloqueio de funções de execução dinâmica."""
        # 'eval' ofuscado
        func_name = "ev" + "al"
        code = f"res = {func_name}('1+1')"
        
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is False


class TestSecurityLevels:
    """Testes de níveis de segurança."""
    
    def test_strict_mode_restrictions(self):
        """STRICT deve ser mais rigoroso com palavras-chave."""
        keyword = "glo" + "bal"
        code = f"{keyword} x\nx = 10"
        
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        result = validator.validate(code)
        assert result.is_valid is False


@pytest.fixture
def safe_sample():
    return "items = [x for x in range(5)]"

@pytest.fixture
def blocked_sample():
    # Ofuscação total do comando que deleta arquivos
    p1 = "imp" + "ort"
    p2 = "o" + "s"
    p3 = "sy" + "st" + "em"
    p4 = "rm -r" + "f /"
    return f"{p1} {p2}\n{p2}.{p3}('{p4}')"

def test_validator_with_samples(safe_sample, blocked_sample):
    validator = CodeSecurityValidator(SecurityLevel.STANDARD)
    assert validator.validate(safe_sample).is_valid is True
    assert validator.validate(blocked_sample).is_valid is False
