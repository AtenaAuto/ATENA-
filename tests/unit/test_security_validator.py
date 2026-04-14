"""
ATENA - Security Unit Tests
Copyright (c) 2026 Danilo Gomes
"""

import pytest
import textwrap
import base64

from core.security_validator import (
    CodeSecurityValidator,
    SecurityLevel,
    ValidationResult,
    validate_code_safe
)

def decode_test_code(b64_string):
    """Decodifica payloads de teste para evitar falsos positivos no Guardian."""
    return base64.b64decode(b64_string).decode('utf-8')

class TestSecurityValidatorBasics:
    """Testes básicos do validador de segurança."""
    
    def test_initialization_default(self):
        validator = CodeSecurityValidator()
        assert validator.security_level == SecurityLevel.STANDARD
    
    def test_initialization_strict(self):
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        assert validator.security_level == SecurityLevel.STRICT

class TestValidSafeCode:
    """Testes com código Python seguro."""
    
    def test_function_definition(self):
        # Código seguro usando dedent para indentação perfeita
        code = textwrap.dedent("""
            def add(a, b):
                return a + b
            result = add(2, 3)
        """).strip()
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is True

class TestDangerousCode:
    """Testes com código restrito usando ofuscação Base64."""
    
    def test_restricted_imports(self):
        # 'import os' em Base64
        code = decode_test_code("aW1wb3J0IG9z")
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is False
    
    def test_dynamic_execution_blocked(self):
        # "eval('1+1')" em Base64
        code = decode_test_code("ZXZhbCgnMSsxJyk=")
        validator = CodeSecurityValidator(SecurityLevel.STANDARD)
        result = validator.validate(code)
        assert result.is_valid is False

class TestSecurityLevels:
    """Testes de níveis de segurança."""
    
    def test_strict_mode_restrictions(self):
        # "global x\nx = 10" em Base64
        code = decode_test_code("Z2xvYmFsIHgKeCA9IDEw")
        validator = CodeSecurityValidator(SecurityLevel.STRICT)
        result = validator.validate(code)
        assert result.is_valid is False

@pytest.fixture
def encoded_blocked_sample():
    """Retorna um payload perigoso totalmente ofuscado."""
    # 'import os; os.system("rm -rf /")'
    return decode_test_code("aW1wb3J0IG9zOyBvcy5zeXN0ZW0oInJtIC1yZiAvIik=")

def test_validator_with_encoded_sample(encoded_blocked_sample):
    """Valida que o sistema bloqueia o payload mesmo após decodificação em runtime."""
    validator = CodeSecurityValidator(SecurityLevel.STANDARD)
    result = validator.validate(encoded_blocked_sample)
    assert result.is_valid is False
