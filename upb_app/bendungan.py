from flask import Blueprint, render_template, request
from upb_app.models import Bendungan, Petugas
from upb_app.models import ManualDaily, ManualTma, ManualVnotch, ManualPiezo
from upb_app.models import Kegiatan, Rencana, BendungAlert, CurahHujanTerkini, wil_sungai
from sqlalchemy import and_, desc, cast, Date, extract
from pprint import pprint
from pytz import timezone
import datetime

bp = Blueprint('bendungan', __name__)


@bp.route('/')
def index():
    ''' Home Bendungan '''
    waduk = Bendungan.query.order_by(Bendungan.wil_sungai, Bendungan.id).all()
    date = request.values.get('sampling')
    def_date = datetime.datetime.now()
    sampling = datetime.datetime.strptime(date, "%Y-%m-%d") if date else def_date
    end = sampling + datetime.timedelta(days=1)

    data = {
        '1': [],
        '2': [],
        '3': []
    }
    count = 1
    for w in waduk:
        daily = ManualDaily.query.filter(
                                    and_(
                                        extract('month', ManualDaily.sampling) == sampling.month,
                                        extract('year', ManualDaily.sampling) == sampling.year,
                                        extract('day', ManualDaily.sampling) == sampling.day),
                                    ManualDaily.bendungan_id == w.id
                                    ).first()
        vnotch = ManualVnotch.query.filter(
                                    and_(
                                        extract('month', ManualVnotch.sampling) == sampling.month,
                                        extract('year', ManualVnotch.sampling) == sampling.year,
                                        extract('day', ManualVnotch.sampling) == sampling.day),
                                    ManualVnotch.bendungan_id == w.id
                                    ).first()
        tma = ManualTma.query.filter(
                                    and_(
                                        extract('month', ManualTma.sampling) == sampling.month,
                                        extract('year', ManualTma.sampling) == sampling.year,
                                        extract('day', ManualTma.sampling) == sampling.day),
                                    ManualTma.bendungan_id == w.id
                                    ).all()
        alert = BendungAlert.query.filter(and_(
                                        extract('month', BendungAlert.sampling) == sampling.month,
                                        extract('year', BendungAlert.sampling) == sampling.year,
                                        extract('day', BendungAlert.sampling) == sampling.day),
                                    BendungAlert.bendungan_id == w.id
                                    ).order_by(BendungAlert.sampling.desc()).all()
        ch_t = CurahHujanTerkini.query.filter(and_(
                                        extract('month', CurahHujanTerkini.sampling) == sampling.month,
                                        extract('year', CurahHujanTerkini.sampling) == sampling.year,
                                        extract('day', CurahHujanTerkini.sampling) == sampling.day),
                                    CurahHujanTerkini.bendungan_id == w.id
                                    ).order_by(CurahHujanTerkini.sampling.desc()).first()

        tma_d = {
            '6': None,
            '12': None,
            '18': None,
        }
        kondisi = ""
        flood = 0
        time = ""
        for t in tma:
            if t.tma:
                spill = t.tma - w.muka_air_normal
                if spill >= flood:
                    flood = spill
                    time = t.sampling.strftime("%H:%M:%S")
            tma_d[f"{t.sampling.hour}"] = None if not t.tma else "{:,.2f}".format(t.tma)

        for al in alert[::-1]:
            spill = al.tma - w.muka_air_normal
            if spill >= flood:
                flood = spill
                time = al.sampling.strftime("%H:%M:%S")

        if round(flood, 2) > 0:
            kondisi = f"<b>Normal</b><br><span style='color: red'>+{round(flood, 3)}</span> <small><i>{time}</i></small>"

        data[w.wil_sungai].append({
            'id': w.id,
            'no': count,
            'nama': w.name,
            'kab': w.kab,
            'volume': "{:,.2f}".format(w.volume/1000000),
            'lbi': "{:,.2f}".format(w.lbi),
            'elev_puncak': "{:,.2f}".format(w.elev_puncak),
            'muka_air_normal': "{:,.2f}".format(w.muka_air_normal),
            'muka_air_min': "{:,.2f}".format(w.muka_air_min),
            'tma6': tma_d['6'],
            'tma12': tma_d['12'],
            'tma18': tma_d['18'],
            'intake_vol': None if not daily else daily.intake_vol,
            'intake_deb': None if not daily else daily.intake_deb,
            'spillway_deb': None if not daily else daily.spillway_deb,
            'debit': None if not vnotch else vnotch.vn1_deb,
            'kondisi': kondisi or "Normal",
            'curahhujan': None if not ch_t else {'ch': ch_t.ch, 'time': ch_t.sampling},
            'tma_banjir': None if not alert else {'tma': alert[0].tma, 'time': alert[0].sampling}
        })
        count += 1

    return render_template('bendungan/index.html',
                            waduk=data,
                            wil_sungai=wil_sungai,
                            sampling=sampling)


@bp.route('/<lokasi_id>', methods=['GET', 'POST'])
def tma(lokasi_id):
    date = request.values.get('sampling')
    def_date = datetime.datetime.utcnow()
    sampling = datetime.datetime.strptime(date, "%Y-%m-%d") if date else def_date
    end = sampling + datetime.timedelta(days=1)

    pos = Bendungan.query.get(lokasi_id)
    tma = ManualTma.query.filter(
                                and_(
                                    ManualTma.sampling >= sampling,
                                    ManualTma.sampling <= end),
                                ManualTma.bendungan_id == pos.id
                            ).order_by(desc(ManualTma.sampling)).first()

    return render_template('bendungan/info.html', waduk=pos, tma=tma)


@bp.route('/<lokasi_id>/operasi', methods=['GET', 'POST'])
def operasi(lokasi_id):
    date = request.values.get('sampling')
    def_date = datetime.datetime.utcnow()
    sampling = datetime.datetime.strptime(date, "%Y") if date else def_date
    end = datetime.datetime.strptime(f"{sampling.year}-11-1", "%Y-%m-%d")
    start = end - datetime.timedelta(days=356)

    pos = Bendungan.query.get(lokasi_id)
    rtow = Rencana.query.filter(
                                and_(
                                    Rencana.sampling >= start,
                                    Rencana.sampling <= end),
                                Rencana.bendungan_id == pos.id
                                ).all()
    tanggal = ""
    operasi = {
        'po_bona': "",
        'po_bonb': "",
        'real': "",
        'elev_min': "",
        'sedimen': "",
        'po_outflow': "",
        'po_inflow': "",
        'real_outflow': "",
        'real_inflow': ""
    }
    for i, rt in enumerate(rtow):
        if (i != 0):
            tanggal += ","
            operasi['po_bona'] += ","
            operasi['po_bonb'] += ","
            operasi['real'] += ","
            operasi['elev_min'] += ","
            operasi['sedimen'] += ","
            operasi['po_outflow'] += ","
            operasi['po_inflow'] += ","
            operasi['real_outflow'] += ","
            operasi['real_inflow'] += ","

        tgl_str = rt.sampling.strftime("%Y-%m-%d")
        tanggal += f"'{tgl_str}'"
        operasi['po_bona'] += f"{rt.po_bona}" if rt.po_bona else "0"
        operasi['po_bonb'] += f"{rt.po_bonb}" if rt.po_bonb else "0"
        operasi['real'] += str(rt.po_bona - 2) if rt.po_bona else "0"
        operasi['elev_min'] += f"{pos.muka_air_min}"
        operasi['sedimen'] += f"{pos.sedimen}"
        operasi['po_outflow'] += '0' if not rt.po_outflow_deb else str(rt.po_outflow_deb)
        operasi['po_inflow'] += '0' if not rt.po_inflow_deb else str(rt.po_inflow_deb)
        operasi['real_outflow'] += "0"
        operasi['real_inflow'] += "0"

    return render_template('bendungan/operasi.html',
                            waduk=pos,
                            sampling=sampling,
                            operasi=operasi,
                            tanggal=tanggal)


@bp.route('/<lokasi_id>/vnotch', methods=['GET', 'POST'])
def vnotch(lokasi_id):
    date = request.values.get('sampling')
    def_date = datetime.datetime.utcnow()
    sampling = datetime.datetime.strptime(date, "%Y") if date else def_date
    end = datetime.datetime.strptime(f"{sampling.year}-11-1", "%Y-%m-%d")
    start = end - datetime.timedelta(days=356)

    pos = Bendungan.query.get(lokasi_id)
    sampling = datetime.datetime.now()

    manual_vn = ManualVnotch.query.filter(
                                        and_(
                                            ManualVnotch.sampling >= start,
                                            ManualVnotch.sampling <= end),
                                        ManualVnotch.bendungan_id == pos.id
                                    ).all()
    manual_daily = ManualDaily.query.filter(
                                        and_(
                                            ManualDaily.sampling >= start,
                                            ManualDaily.sampling <= end),
                                        ManualDaily.bendungan_id == pos.id
                                    ).all()
    filtered_daily = {}
    for daily in manual_daily:
        filtered_daily[daily.sampling.strftime("%Y-%m-%d")] = daily
    filtered_vnotch = {}
    for vn in manual_vn:
        tgl = vn.sampling.strftime("%Y-%m-%d")
        if tgl not in filtered_vnotch:
            filtered_vnotch[tgl] = {
                'ch': 0,
                'vn': {
                    'VNotch 1': vn.vn1_deb,
                    'VNotch 2': vn.vn2_deb,
                    'VNotch 3': vn.vn3_deb
                }
            }
        filtered_vnotch[tgl]['ch'] += filtered_daily[tgl].ch or 0

    vnotch = {
        'tanggal': "",
        'ch': "",
        'vn': {}
    }
    for i, vn in enumerate(filtered_vnotch):
        if i != 0:
            vnotch['tanggal'] += ","
            vnotch['ch'] += ","
            for vnn in filtered_vnotch[vn]['vn']:
                vnotch['vn'][vnn] += ","

        tgl = vn
        vnotch['tanggal'] += f"'{tgl}'"
        vnotch['ch'] += f"{filtered_vnotch[vn]['ch']}"
        for vnn in filtered_vnotch[vn]['vn']:
            if vnn not in vnotch['vn']:
                vnotch['vn'][vnn] = ""
            val = "0" if not filtered_vnotch[vn]['vn'][vnn] else filtered_vnotch[vn]['vn'][vnn]
            vnotch['vn'][vnn] += f"{val}"
    # pprint(vnotch)

    return render_template('bendungan/vnotch.html',
                            waduk=pos,
                            sampling=sampling,
                            vnotch=vnotch)


@bp.route('/<lokasi_id>/piezo', methods=['GET', 'POST'])
def piezo(lokasi_id):
    date = request.values.get('sampling')
    def_date = datetime.datetime.utcnow()
    sampling = datetime.datetime.strptime(date, "%Y") if date else def_date
    end = datetime.datetime.strptime(f"{sampling.year}-11-1", "%Y-%m-%d")
    start = end - datetime.timedelta(days=356)

    pos = Bendungan.query.get(lokasi_id)
    sampling = datetime.datetime.now()

    manual_piezo = ManualPiezo.query.filter(
                                            and_(
                                                ManualPiezo.sampling >= start,
                                                ManualPiezo.sampling <= end),
                                            ManualPiezo.bendungan_id == pos.id
                                        ).all()
    profile = ['1', '2', '3', '4', '5']
    alpha = ['a', 'b', 'c']
    tgl_labels = ""
    piezodata = {}
    for p in profile:
        piezodata[p] = {}
        for a in alpha:
            piezodata[p][a] = ""

    for i, piezo in enumerate(manual_piezo):
        if i == 0:
            tgl_labels += f"'{piezo.sampling.strftime('%d %b %Y')}'"
            for p in profile:
                for a in alpha:
                    val = getattr(piezo, f"p{p}{a}")
                    val = val or "0"
                    piezodata[p][a] += f"{val}"
            continue

        tgl_labels += f",'{piezo.sampling.strftime('%d %b %Y')}'"
        for p in profile:
            for a in alpha:
                val = getattr(piezo, f"p{p}{a}")
                val = val or "0"
                piezodata[p][a] += f",{val}"
    # pprint(piezodata)

    return render_template('bendungan/piezo.html',
                            waduk=pos,
                            sampling=sampling,
                            tgl_labels=tgl_labels,
                            piezodata=piezodata)


@bp.route('/petugas')
def petugas():
    waduk = Bendungan.query.all()
    petugas = Petugas.query.all()

    data = {}
    for w in waduk:
        arr = w.nama.split('_')
        name = f"{arr[0].title()}.{arr[1].title()}"
        data[w.id] = {
            'nama': name,
            'petugas': []
        }
    for p in petugas:
        data[p.bendungan.id]['petugas'].append({
            'nama': p.nama,
            'tugas': p.tugas
        })

    return render_template('bendungan/petugas.html',
                            data=data)


@bp.route('/kegiatan')
def kegiatan():
    date = request.values.get('sampling')
    def_date = date if date else datetime.datetime.now().strftime("%Y-%m-%d")
    sampling = datetime.datetime.strptime(def_date, "%Y-%m-%d")
    end = sampling + datetime.timedelta(hours=23, minutes=55)

    kegiatan = Kegiatan.query.filter(
                                and_(
                                    Kegiatan.sampling >= sampling,
                                    Kegiatan.sampling <= end)
                                ).order_by(Kegiatan.c_date).all()
    data = {}
    for keg in kegiatan:
        if keg.bendungan_id not in data:
            data[keg.bendungan_id] = {
                'bend': keg.bendungan,
                'kegiatan': {

                }
            }

        if keg.petugas not in data[keg.bendungan_id]['kegiatan']:
            data[keg.bendungan_id]['kegiatan'][keg.petugas] = []

        data[keg.bendungan_id]['kegiatan'][keg.petugas].append(keg)

    return render_template('bendungan/kegiatan.html',
                            data=data,
                            sampling=sampling)
