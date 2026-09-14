"""Datos candidatos del QR; no autentica ante ARCA ni decide crédito fiscal."""
import base64
import json
import re
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse, parse_qs

VERSION = 'campos/2.1'


def entero_fiscal(value, minimum, maximum):
    # int(1.9) truncaría silenciosamente un dato documental inválido.
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        raise ValueError('Identificador fiscal no entero')
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError('Identificador fiscal fuera de rango')
    return result


def candidatos_texto(pagina):
    """Conserva alternativas y su evidencia; nunca corrige dígitos por parecido."""
    result = {k: [] for k in ('cuits','numeros','autorizaciones','fechas','totales')}
    def add(field, value, source, match):
        entry = {'valor':value, 'fuente':source, 'evidencia':match.group(0)}
        if entry not in result[field]:
            result[field].append(entry)
    for source in ('texto_nativo','texto','texto_alternativo'):
        text = pagina.get(source,'') or ''
        for match in re.finditer(r'(?<!\d)(\d{2})[-.\s]?(\d{8})[-.\s]?(\d)(?!\d)',text):
            value = ''.join(match.groups())
            digits = list(map(int,value))
            check = 11-sum(a*b for a,b in zip(digits[:10],[5,4,3,2,7,6,5,4,3,2]))%11
            check = 0 if check==11 else 9 if check==10 else check
            if check==digits[-1]:
                add('cuits',value,source,match)
        for match in re.finditer(r'(?<!\d)(\d{4,5})\s*[-–]\s*(\d{6,8})(?!\d)',text):
            add('numeros',[int(match[1]),int(match[2])],source,match)
        for match in re.finditer(r'(?:N[°º*“]?|Nro\.?)[ \t:]*(\d{4,5})[ \t]+(\d{6,8})(?!\d)',text,re.I):
            add('numeros',[int(match[1]),int(match[2])],source,match)
        for match in re.finditer(r'Punto de venta\s*:\s*(\d{1,5})\s*Comp\.?\s*Nro\s*:\s*(\d{1,8})',text,re.I):
            add('numeros',[int(match[1]),int(match[2])],source,match)
        for match in re.finditer(r'\bCAE(?:A)?\s*(?:N(?:ro)?[°º*.:]*)?[\s:]*([0-9]{14})(?!\d)',text,re.I):
            add('autorizaciones',match[1],source,match)
        for match in re.finditer(r'(?<!\d)(\d{1,2})/(\d{1,2})/(20\d{2})(?!\d)',text):
            try:
                value = date(int(match[3]),int(match[2]),int(match[1])).isoformat()
            except ValueError:
                continue
            add('fechas',value,source,match)
        # Sólo TOTAL solo en su línea: excluye subtotal, total IVA y pagos.
        for match in re.finditer(r'(?im)^\s*TOTAL\s*[:$]?\s*\$?\s*(\d[\d.,]*[.,]\d{2})(?![\d.,])',text):
            token = match[1]
            separator = token[-3]
            whole = token[:-3].replace(',','').replace('.','')
            if whole.isdigit() and separator in ',.':
                add('totales',int(whole)*100+int(token[-2:]),source,match)
    return result


def extraer(pagina):
    candidates, errors = [], []
    for code in pagina.get('codigos', []):
        try:
            if not isinstance(code,str) or len(code)>16384:
                raise ValueError('Código inválido o demasiado largo')
            url = urlparse(code)
            if url.hostname not in {'www.afip.gob.ar','afip.gob.ar','www.arca.gob.ar','arca.gob.ar'} or url.path != '/fe/qr/':
                continue
            if url.scheme not in {'http','https'} or url.username or url.password:
                raise ValueError('URL fiscal inválida')
            encoded = parse_qs(url.query)['p'][0]
            data = json.loads(base64.b64decode(encoded, validate=True), parse_float=Decimal)
            if not isinstance(data,dict):
                raise ValueError('Contenido QR no es un objeto')
            date.fromisoformat(data['fecha'])
            cents = Decimal(str(data['importe'])) * 100
            if not cents.is_finite() or cents != cents.to_integral_value() or cents < 0:
                raise ValueError('Importe QR inválido')
            cuit = str(data['cuit'])
            if not re.fullmatch(r'\d{11}',cuit):
                raise ValueError('CUIT QR inválido')
            digits = list(map(int,cuit))
            check = 11 - sum(a*b for a,b in zip(digits[:10],[5,4,3,2,7,6,5,4,3,2])) % 11
            check = 0 if check == 11 else 9 if check == 10 else check
            if check != digits[-1]:
                raise ValueError('Dígito verificador CUIT inválido')
            candidate = {'cuit': cuit, 'fecha': data['fecha'], 'tipo': entero_fiscal(data['tipoCmp'],1,999),
                'punto_venta': entero_fiscal(data['ptoVta'],1,99999), 'numero': entero_fiscal(data['nroCmp'],1,99999999),
                'total_centavos': int(cents), 'moneda': data['moneda'],
                'autorizacion': str(data.get('codAut','')), 'tipo_autorizacion': data.get('tipoCodAut'),
                'receptor': str(data.get('nroDocRec',''))}
            if candidate['punto_venta'] < 1 or candidate['numero'] < 1:
                raise ValueError('Numeración QR inválida')
            if candidate not in candidates:
                candidates.append(candidate)
        except (ValueError,KeyError,TypeError) as exc:
            errors.append(f'QR_INVALIDO: {exc}')
    text_fields = candidatos_texto(pagina)
    totals = {entry['valor'] for entry in text_fields['totales']}
    if len(totals)>1:
        errors.append('TOTALES_OCR_DIVERGENTES')
    if len(candidates)>1:
        errors.append('MULTIPLES_COMPROBANTES_QR_EN_PAGINA')
    if len(candidates)==1:
        if totals and totals != {candidates[0]['total_centavos']}:
            errors.append('CONTRADICCION_TOTAL_OCR_QR')
        auths = {entry['valor'] for entry in text_fields['autorizaciones']}
        if auths and candidates[0]['autorizacion'] and auths != {candidates[0]['autorizacion']}:
            errors.append('CONTRADICCION_AUTORIZACION_OCR_QR')
    return {'version':VERSION, 'qr': candidates, 'texto':text_fields, 'advertencias': errors,
            'estado': 'CANDIDATO_QR' if len(candidates)==1 and not errors else 'REVISAR'}
