'''
Gera relatorios de matching em tres formatos:
- XLSX
- PDF
- CSV
    
    
'''
from __future__ import annotations
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import HRFlowable, SimpleDocTemplate, Table, Spacer, TableStyle
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Side, Border
from app.logs.config import logger


COR_VERDE      = "00A86B"
COR_VERMELHO   = "D32F2F"
COR_AMARELO    = "F9A825"
COR_AZUL_ESCURO = "1565C0"
COR_CINZA      = "F5F5F5"
COR_CABECALHO  = "1A237E"

#XLSX
def export_xlsx(data: dict) -> bytes:
    """
    Docstring para export_xlsx
    
    :param data: Descrição
    :type data: dict
    :return: Descrição
    :rtype: bytes(planilha do excel)
    """
    wb = Workbook()
    _build_resumo_sheet(wb, data)
    _