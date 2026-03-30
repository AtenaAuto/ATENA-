#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de utilidades básicas com boas práticas.
"""

import logging
from typing import Union, Optional

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def saudacao(nome: Optional[str] = None) -> str:
    """
    Retorna uma saudação personalizada.

    Args:
        nome (str, opcional): Nome da pessoa a ser saudada. Se não fornecido,
                              usa uma saudação genérica.

    Returns:
        str: Mensagem de saudação.

    Example:
        >>> saudacao("Maria")
        'Olá, Maria! Bem-vindo(a) ao módulo.'
        >>> saudacao()
        'Olá! Seja bem-vindo(a) ao módulo.'
    """
    if nome:
        msg = f"Olá, {nome}! Bem-vindo(a) ao módulo."
    else:
        msg = "Olá! Seja bem-vindo(a) ao módulo."
    
    logger.info(f"Saudação gerada para: {nome or 'anônimo'}")
    return msg


def soma(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Calcula a soma de dois números.

    Args:
        a (int, float): Primeiro número.
        b (int, float): Segundo número.

    Returns:
        int ou float: Resultado da soma.

    Raises:
        TypeError: Se algum dos argumentos não for numérico.

    Example:
        >>> soma(3, 5)
        8
        >>> soma(2.5, 1.5)
        4.0
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError(f"Ambos os argumentos devem ser números. Recebidos: {type(a)}, {type(b)}")
    
    resultado = a + b
    logger.debug(f"Soma: {a} + {b} = {resultado}")
    return resultado


# ──────────────────────────────────────────────────────────────────────
# Opção com classe (para projetos maiores)
# ──────────────────────────────────────────────────────────────────────

class Calculadora:
    """Classe utilitária para operações matemáticas básicas."""

    @staticmethod
    def somar(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Soma dois números."""
        return soma(a, b)

    @staticmethod
    def saudacao(nome: Optional[str] = None) -> str:
        """Gera uma saudação."""
        return saudacao(nome)


# ──────────────────────────────────────────────────────────────────────
# Exemplo de uso (executado apenas quando o script é rodado diretamente)
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import doctest
    doctest.testmod()  # Verifica os exemplos das docstrings
    
    print(saudacao("Usuário"))
    print(f"3 + 5 = {soma(3, 5)}")
    
    # Usando a classe
    calc = Calculadora()
    print(calc.saudacao("Dev"))
    print(f"2.5 + 1.5 = {calc.somar(2.5, 1.5)}")
