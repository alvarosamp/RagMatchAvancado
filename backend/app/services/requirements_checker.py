from sqlalchemy.orm import Session

from app.db.models import Product
from app.logs.config import logger

# Dicionário de requisitos (baseado no edital)
REQUIREMENTS = {
    "portas_rj45": "16 portas",  # Exemplo de como o requisito é descrito no edital
    "gerenciavel": "sim",
    "poe": "sim",
    "velocidade_porta_mbps": "1000 Mbps",
    "alimentacao_bivolt": "sim",
    "certificacao_anatel": "sim",
}


def check_requirements(switch_specs: dict) -> dict:
    """
    Função que compara os requisitos do switch com o edital.
    
    :param switch_specs: especificações do switch a ser verificado.
    :return: dicionário com o status de cada requisito.
    """
    result = {}
    
    for key, requirement in REQUIREMENTS.items():
        if key in switch_specs:
            # Se o requisito for um número (exemplo: PoE ou capacidade de comutação)
            if isinstance(requirement, int) and isinstance(switch_specs[key], int):
                if switch_specs[key] >= requirement:
                    result[key] = {"status": "✅ Atende", "details": f"{switch_specs[key]} ≥ exigido"}
                else:
                    result[key] = {"status": "❌ Não atende", "details": f"{switch_specs[key]} < exigido"}
            # Se o requisito for uma string (exemplo: portas, gerenciável, etc)
            elif switch_specs[key] == requirement:
                result[key] = {"status": "✅ Atende", "details": f"{requirement} ≥ exigido"}
            else:
                result[key] = {"status": "❌ Não atende", "details": f"{switch_specs[key]} ≠ fornecido"}
        else:
            result[key] = {"status": "⚠️ Verificar", "details": "Requisito não encontrado"}

    logger.info(f"Verificação de requisitos completada: {result}")
    return result


# Exemplo de como usar essa função com o banco de dados
def verify_switch_requirements(db: Session):
    """
    Verifica se os switches no banco de dados atendem aos requisitos.
    """
    switches = db.query(Product).filter(Product.category == "switch").all()
    
    for switch in switches:
        switch_data = switch.data  # switch.data contém as especificações do switch
        
        # Verifica os requisitos para o switch
        verification_result = check_requirements(switch_data)
        
        # Loga o resultado da verificação
        logger.info(f"Resultado da verificação para {switch.model}: {verification_result}")
        
    return {"message": "Verificação completa", "switches_verified": len(switches)}
