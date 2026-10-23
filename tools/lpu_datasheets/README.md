# Catálogo técnico da LPU — sem IA

Este pacote identifica todos os produtos da LPU e salva **um JSON por produto na pasta `produtos/`**. O match não usa IA. Nenhuma chave de API é necessária.

Quando não há datasheet com identificação exata, o JSON utiliza **todos os dados técnicos disponíveis na LPU**, conforme solicitado. `fallback_lpu: true` e `fonte_principal_especificacoes: "lpu"` indicam esse caso. A descrição original é preservada inteira, além dos valores que as regras conseguem estruturar. Informações que a LPU não fornece continuam desconhecidas.

## Conteúdo

- `produtos/`: JSONs individuais, identificadores, descrições originais, origem/linha da LPU, características estruturadas por regras, texto e tabelas completos dos PDFs associados.
- `datasheets/`: cópias dos PDFs. Nomes SHA-256 evitam colisões e identificam precisamente a fonte.
- `documentos/`: transcrição de cada PDF único, com páginas e tabelas.
- `relatorio.csv`: índice para localizar cada produto, JSON e situação da coleta.
- `pendencias.json`: produtos sem identificação exata em uma ficha.
- `erros.json`: erros de download/leitura, inclusive URLs tentadas que não existem.
- `inventario.json`: produtos deduplicados por marca + código de fabricante; repetições da LPU preservadas como origem.
- `scripts/`: os scripts e configuração reproduzíveis.

## Limites de completude — ler antes de usar no filtro

**Ter um arquivo JSON não significa ter todas as especificações confirmadas.** O status informa se uma ficha contendo o identificador exato foi localizada. Nenhum produto é automaticamente declarado completo.

Os campos `especificacoes_tecnicas` têm `nome`, `valor`, `unidade`, `condicao`, `fonte` e `validacao`. Valores da LPU são identificados como `informado_na_lpu`. Características dos PDFs são `revisar_aplicabilidade`: precisam de confirmação de modelo, revisão, região, variante e coluna antes de virarem critérios de filtro. Marque como `validado_manual` somente após conferir a fonte. Nunca trate ausência como zero ou "não suporta".

Textos e tabelas integrais estão em `transcricao_integral`. Uma ficha de família pode mencionar vários modelos, ou o código X pode representar variantes C/I. O coletor não troca esses sufixos nem junta modelos de alimentação AC/DC, alcance ou comprimento distintos. Equivalências entre código TOR e fabricante aparecem como candidatos para revisão. PDFs locais não têm autenticidade presumida; sua origem fica registrada. Diagramas, textos em imagens, páginas escaneadas e texto rotacionado podem exigir leitura visual/OCR. Não há OCR neste script.

As tabelas são transcritas mantendo limites mínimo/típico/máximo, símbolos e notas quando legíveis. A estruturação por regras não transforma automaticamente todas as tabelas em valores escalares. A validação de evidência não garante que o documento esteja atualizado ou que uma característica se aplique à revisão comprada.

## Executar no Mac

Python 3.10 ou superior:

`executar.py` reúne coleta e estruturação: recebe os mesmos argumentos de `coletar.py` e gera os JSONs técnicos ao final. A configuração `fontes_coletadas.json`, incluída no pacote entregue, reúne as URLs oficiais aproveitadas nesta coleta; pode ser usada com `--sources fontes_coletadas.json`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

python3 coletar.py \
  --xlsx "/Users/alvarosamp/Downloads/LPU - REV-09_10_26 - Versão Vendas - Válido até 30_10_26.xlsx" \
  --output "/Volumes/Untitled/TOR/LPU_2026-10-14" \
  --local "/Volumes/Untitled/Datasheet" \
  --local "/Volumes/Untitled/TOR/Datasheet" \
  --local "/Volumes/Untitled/TOR/datasheets2" \
  --local "/Volumes/Untitled/TOR/switches" \
  --local "/Volumes/Untitled/TOR/RC_DS_RAX721-C_202312.pdf" \
  --online --precision

python3 estruturar.py --output "/Volumes/Untitled/TOR/LPU_2026-10-14"
```

Não reexecute sobre uma pasta com revisão manual dos JSONs: a coleta/estruturação regenera esses arquivos. Use outra pasta para uma nova coleta e compare os resultados.

## Completar faltantes

1. Consulte `pendencias.json` e `consulta_sugerida` no JSON individual.
2. Obtenha a ficha exata no fabricante/fornecedor, inclusive acessórios e variantes sem documentação pública.
3. Acrescente URLs oficiais em `fontes.json`, ou salve os PDFs em uma pasta e passe outro `--local`.
4. Execute em uma nova pasta. PDFs já extraídos são reutilizados se a pasta anterior for usada sem revisões manuais.
5. Confira visualmente as fichas e valide as características que alimentarão seu filtro. Para acrescentar um valor ausente, use o mesmo formato das características e registre página, evidência e condição.

O modo online consulta as URLs cadastradas, segue links PDF dessas páginas e tenta a convenção de URLs Precision quando `--precision` é usado. **Não é uma busca universal na internet** e não garante encontrar todos os produtos. Erros de URLs previstas são registrados; um HTTP 200 sem PDF não é considerado datasheet.

## Fontes oficiais iniciais

- [Raisecom — documentação](https://www.raisecom.com.br/documentacao/)
- [TP-Link — EAP653](https://static.tp-link.com/upload/product-overview/2025/202510/20251027/Datasheet_EAP653.pdf)
- [Precision — PRE-SFP-TM](https://www.precisionot.com/wp-content/uploads/pre-sfp-tm.pdf)
- [Precision — guia de produtos](https://www.precisionot.com/PrecisionOT-ProductGuide.pdf)
- [Ubiquiti — UACC-CM-RJ45-MG](https://dl.ui.com/ds/uacc-cm-rj45-mg_ds.pdf)
