#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω - Módulo de Síntese de Proteínas e Análise de Mutações (SPAM)
Skill de Biotecnologia integrada para análise genômica.
"""

import json
from datetime import datetime

class AtenaBiotechSPAM:
    def __init__(self):
        # Tabela de Códons (RNA -> Aminoácido)
        self.codon_table = {
            'AUA':'I', 'AUC':'I', 'AUU':'I', 'AUG':'M',
            'ACA':'T', 'ACC':'T', 'ACG':'T', 'ACU':'T',
            'GUA':'V', 'GUC':'V', 'GUG':'V', 'GUU':'V',
            'GCA':'A', 'GCC':'A', 'GCG':'A', 'GCU':'A',
            'UUA':'L', 'UUG':'L', 'CUA':'L', 'CUC':'L', 'CUG':'L', 'CUU':'L',
            'UCA':'S', 'UCC':'S', 'UCG':'S', 'UCU':'S',
            'UUC':'F', 'UUU':'F', 'UUA':'L', 'UUG':'L',
            'UAC':'Y', 'UAU':'Y', 'UAA':'_', 'UAG':'_',
            'UGC':'C', 'UGU':'C', 'UGA':'_', 'UGG':'W',
            'CAA':'Q', 'CAG':'Q', 'CAU':'H', 'CAC':'H',
            'CGA':'R', 'CGC':'R', 'CGG':'R', 'CGU':'R',
            'GAA':'E', 'GAG':'E', 'GAU':'D', 'GAC':'D',
            'GGA':'G', 'GGC':'G', 'GGG':'G', 'GGU':'G',
            'AGC':'S', 'AGU':'S', 'AGA':'R', 'AGG':'R',
            'AAC':'N', 'AAU':'N', 'AAA':'K', 'AAG':'K',
        }

    def transcribe(self, dna_sequence):
        """Converte DNA em mRNA (Troca T por U)."""
        return dna_sequence.upper().replace('T', 'U')

    def translate(self, mrna_sequence):
        """Traduz mRNA em uma sequência de aminoácidos."""
        protein = ""
        for i in range(0, len(mrna_sequence) - (len(mrna_sequence) % 3), 3):
            codon = mrna_sequence[i:i+3]
            amino_acid = self.codon_table.get(codon, '?')
            if amino_acid == '_': # Stop codon
                break
            protein += amino_acid
        return protein

    def analyze_mutation(self, original_dna, mutated_dna):
        """Identifica mutações pontuais e seu impacto na proteína."""
        mrna_orig = self.transcribe(original_dna)
        mrna_mut = self.transcribe(mutated_dna)
        
        prot_orig = self.translate(mrna_orig)
        prot_mut = self.translate(mrna_mut)
        
        mutations = []
        for i in range(min(len(original_dna), len(mutated_dna))):
            if original_dna[i] != mutated_dna[i]:
                mutations.append({
                    "position": i + 1,
                    "from": original_dna[i],
                    "to": mutated_dna[i]
                })
        
        impact = "Sinônima" if prot_orig == prot_mut else "Não-Sinônima (Alteração de Proteína)"
        if len(prot_mut) < len(prot_orig):
            impact = "Nonsense (Parada Precoce)"
            
        return {
            "mutations_found": mutations,
            "original_protein": prot_orig,
            "mutated_protein": prot_mut,
            "impact": impact
        }

def main():
    print("🧬 ATENA Ω: Iniciando Análise Biotecnológica...")
    biotech = AtenaBiotechSPAM()
    
    # Exemplo: Sequência do gene da Insulina (fragmento simplificado)
    dna_ref = "ATGGCCCTGTGGATGCGCCTCCTGCCCCTGCTGGCCCTGCTGGCCCTCTGGGGACCTGACCCAGCCGCAGCCTTTGTGAACCAACACCTGTGCGGCTCACACCTGGTGGAAGCTCTCTACCTAGTGTGCGGGGAACGAGGCTTCTTCTACACACCCAAGACCCGCCGGGAGGCAGAGGACCTGCAGGTGGGGCAGGTGGAGCTGGGCGGGGGCCCTGGTGCAGGCAGCCTGCAGCCCTTGGCCCTGGAGGGGTCCCTGCAGAAGCGTGGCATTGTGGAACAATGCTGTACCAGCATCTGCTCCCTCTACCAGCTGGAGAACTACTGCAACTAG"
    
    # Simula uma mutação pontual (G -> A na posição 4) que altera o códon GCC para ACC
    # Original: ATG GCC ... (Met Ala)
    # Mutado: ATG ACC ... (Met Thr)
    dna_mut = dna_ref[:3] + "A" + dna_ref[4:]
    
    result = biotech.analyze_mutation(dna_ref, dna_mut)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "analysis": "Síntese e Mutação de Proteína",
        "results": result,
        "status": "Concluído"
    }
    
    print(f"Impacto da Mutação: {result['impact']}")
    print(f"Mutações Detectadas: {len(result['mutations_found'])}")
    
    with open("/home/ubuntu/ATENA-/analysis_reports/biotech_report.json", "w") as f:
        json.dump(report, f, indent=4)

if __name__ == "__main__":
    main()
