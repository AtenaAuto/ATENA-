#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_local_lm import AtenaUltraBrain


def test_simbrain_greeting_returns_human_text():
    brain = AtenaUltraBrain()
    answer = brain._simulate_thinking("Oi Atena, tudo bem?")
    assert "SimBrain" in answer
    assert "pronta para ajudar" in answer
    assert "Processando tarefa" not in answer


def test_simbrain_generic_fallback_mentions_prompt():
    brain = AtenaUltraBrain()
    answer = brain._simulate_thinking("Me ajude a organizar tarefas da sprint")
    assert "Entendi sua solicitação" in answer
    assert "Me ajude a organizar tarefas da sprint" in answer
