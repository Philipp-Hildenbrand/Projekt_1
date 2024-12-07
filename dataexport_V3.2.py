#       ___         __ _
#     / ___|      / _| |  _      ____   _    ___
#    \___ \ / _ \| |_| __\ \ /\ / / _` | '__/ _ \
#     ___) | (_) |  _| |_ \ V  V / (_| | | |  __/
#    |____/ \___/|_|  \__| \_/\_/ \__,_|_|  \___|
# Import von nötiger Software
import locale, requests, time, os#, RPi.GPIO as GPIO
from datetime import datetime

#GPIO.setup(17, GPIO.OUT)
#GPIO.output(17, False)

# Grundwerte
heiz = 0
skip = 0
offset = time.time()
delay = 2
intervall = 5

# Konfiguration
solar_ip1 = "192.168.178.35"
solar_ip2 = "192.168.250.181"
heizon = -6500
heizoff = -100

netz_values = []
akku_values = []

# JSON-Auslesung
def get_data_from_url(ip, endpoint):
    """Ruft Daten von einer URL ab und gibt sie als JSON zurück. Gibt None zurück bei Fehler."""
    url = f"http://{ip}/{endpoint}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return None                             # Bei Fehler None zurückgeben

# Code
while True:
    offset += intervall
    actualtime = datetime.now().strftime("%H:%M:%S")

    # Daten auslesen
    power_data = get_data_from_url(solar_ip1, "solar_api/v1/GetPowerFlowRealtimeData.fcgi")
    if power_data:
        load = power_data['Body']['Data']['Site']['P_Load']
        pv1 = power_data['Body']['Data']['Site']['P_PV']
        g_akku = power_data['Body']['Data']['Site']['P_Akku']
        g_netz = power_data['Body']['Data']['Site']['P_Grid']
        soc = power_data['Body']['Data']['Inverters']['1']['SOC']
    else:
        skip = 1

    storage_data = get_data_from_url(solar_ip1, "solar_api/v1/GetStorageRealtimeData.cgi")
    if storage_data:
        batterytemp = storage_data['Body']['Data']['0']['Controller']['Temperature_Cell']
        batteryvoltage = storage_data['Body']['Data']['0']['Controller']['Voltage_DC']
    else:
        batterytemp = 0
        batteryvoltage = 0

    meter_data = get_data_from_url(solar_ip1, "solar_api/v1/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0")
    if meter_data:
        netzfrequency = meter_data['Body']['Data']['Frequency_Phase_Average']
    else:
        netzfrequency = 0

    power_data2 = get_data_from_url(solar_ip2, "solar_api/v1/GetPowerFlowRealtimeData.fcgi")
    if power_data2:
        pv2 = power_data2['Body']['Data']['Site']['P_PV']
    else:
        pv2 = 0

    #Glättungen
    netz_values.append(g_netz)
    if len(netz_values) > 9:
        netz_values.pop(0)
    netz = sum(netz_values) / len(netz_values)

    akku_values.append(g_akku)
    if len(akku_values) > 9:
        akku_values.pop(0)
    akku = sum(akku_values) / len(akku_values)

    #Berechnungen (Eigenverbrauch, pv)
    pv = pv2 + pv1 + 1
    selfprozent = (100 / pv * load) if pv != 0 else 100

    selfconsumption = max(0, min(100, 100 - selfprozent))

    # Berechnung der Autonomie
    if load != 0:
        autoprozent = -100 / load                   # Prozentualer Netzbezug
    else:
        autoprozent = 0                             # Kein Verbrauch = keine Netzabhängigkeit

    autonomy1 = autoprozent * netz                  # Autonomie anhand der Netzleistung
    autonomy = max(0, min(100, 100 - autonomy1))    # Begrenzung auf 0-100%
    if autonomy == 1.4210854715202004e-14:
        autonomy = 0.0

    pv = pv - 1

    # Steuerung des Heizsystems (GPIO)
    if heiz == 0 and netz < heizon:
        heiz = 1
        # GPIO.output(17, True)                     # Heizsystem einschalten
    if heiz == 1 and netz > heizoff:
        heiz = 0
        # GPIO.output(17, False)                    # Heizsystem ausschalten

    if pv < 0 and akku < 0:
        autonomy = 0.0

    vent = 0
    oftemp = 0
    ofsound = 0

    # Ausgabe in der Konsole
    print(f"{actualtime} {load:.1f} {pv:.1f} {netz:.1f} {akku:.1f} {soc} {batterytemp} {batteryvoltage} {netzfrequency} {selfconsumption} {autonomy:.1f} {heiz} {vent} {oftemp} {ofsound}")

    # Speichern der Daten in eine Datei mit aktuellem Datum im Namen
    directory = os.path.join("heizungssteuerung/livehistory")
    year = datetime.now().strftime("%Y")
    half_path = os.path.join(directory, year)
    if not os.path.exists(half_path):
        os.makedirs(half_path)
    current_date = datetime.now().strftime("%d-%m-%Y")
    file_name = f"{current_date}.txt"
    file_path = os.path.join(directory, year, file_name)

    # Daten in die Datei schreiben
    with open(file_path, 'a') as datopend:          # 'a' für Anhängen, nicht überschreiben
        if skip == 0:
            datopend.write(f"{actualtime} | {load:.1f} | {pv:.1f} | {netz:.1f} | {akku:.1f} | {soc} | {batterytemp} | {batteryvoltage} | {netzfrequency} | {selfconsumption} | {autonomy:.1f} | {heiz} | {vent} | {oftemp} | {ofsound}\n")
        else:
            skip = 0
            print("skip")

    # Verhindert zu schnelles Ausführen des Codes
    sleep_time = offset - time.time()
    if sleep_time > 0:
        time.sleep(sleep_time)