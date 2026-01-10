
NEWACCOUNT="""ACCOUNT;NEUTRAL;FIXED;COPYGRAPHS;VERSION
"10000.0";"10.0";"true";"false";"0.1"
"""

NEWSETUPS="""SETUP;DESCR
"ReboteH1";"Separado ZC H4 pero rebote claro en ZCH1"
"ReboteH4";"entrada fuerza tras rebote 4H previo"
"ScalpAZC";"con ZC ancha y precio separado de ZC operacion en contra hasta ZC en fin de impulso."
"""

NEWFEATURES="""FEATURE;DESCR;SETUPS
"1ra vela";"En primera vela de fuerza, no se marca si ya hay muchas antes de llegar a muro";""
"Apertura";"En apertura";""
"ApoyoD";"Apoyo en ZC Diario";"ReboteH4"
"ApoyoH1";"apoyo en ZC H1";"ReboteH1;ReboteH4;"
"ApoyoH4";"Apoyo en ZC de 4H";""
"Corr";"operando una corrección";""
"""

NEWINSTRUMENTS="""INSTRUMENT;AKA;CURRENCY;PIP;STOPPIPS;SCALE;DIARY;CANDLEH4;CANDLE144;SPREAD;SREADPM
"AEX";"AEX";"EUR";"1.0";"3.0";"1000.0";"9.5";"4.9";"0.2";"0.2";""
"CADCHF";"CADCHF";"CHF";"0.0001";"10.0";"10000.0";"33.0";"18.0";"1.47";"3.0";""
"CL";"CL";"USD";"1.0";"21.0";"8000.0";"170.0";"91.0";"7.0";"2.5";""
"DAX";"DAX";"EUR";"1.0";"42.0";"26000.0";"315.0";"91.5";"12.2";"2.0";""
"DOW";"DOW";"USD";"1.0";"131.0";"47000.0";"448.0";"176.0";"17.5";"3.0";""
"EURCAD";"EURCAD";"CAD";"0.0001";"21.0";"18000.0";"80.0";"34.0";"3.25";"2.5";""
"EURGBP";"EURGBP";"GBP";"0.0001";"6.0";"10000.0";"38.0";"17.0";"1.5";"2.0";""
"EURJPY";"EURJPY";"JPY";"0.01";"140.0";"18000.0";"116.0";"53.0";"4.2";"2.0";""
"EURUSD";"EURUSD";"USD";"0.0001";"13.0";"12000.0";"71.9";"30.0";"3.0";"0.0";""
"FTSE";"FTSE";"EUR";"1.0";"11.0";"10000.0";"75.4";"34.0";"3.2";"1.0";""
"GBPHUF";"GBPHUF";"GBP";"0.01";"935.0";"60000.0";"309.0";"170.0";"20.0";"50.0";""
"GBPJPY";"GBPJPY";"JPY";"0.01";"19.0";"20000.0";"121.0";"63.0";"5.0";"2.0";""
"GBPSEK";"GBPSEK";"SEK";"0.0001";"195.0";"140000.0";"823.0";"400.0";"40.0";"80.0";""
"GBPUSD";"GBPUSD";"GBP";"0.0001";"13.0";"15000.0";"83.3";"37.5";"3.3";"1.0";""
"IBEX";"IBEX";"EUR";"1.0";"44.0";"16000.0";"185.0";"55.7";"6.8";"5.0";""
"MIB";"MIB";"EUR";"1.0";"134.0";"44000.0";"600.0";"175.0";"20.1";"20.0";""
"NASDAQ";"NASDAQ";"USD";"1.0";"88.0";"24000.0";"250.0";"112.0";"11.0";"1.0";""
"OMX";"OMX";"EUR";"1.0";"10.0";"3000.0";"1.0";"1.0";"1.0";"1.0";""
"ORO";"ORO";"USD";"1.0";"11.0";"3700.0";"42.0";"11.6";"1.7";"0.3";""
"PLATA";"PLATA";"USD";"1.0";"13.0";"3800.0";"65.0";"26.5";"2.2";"2.0";""
"PXI";"PXI";"EUR";"1.0";"14.0";"8500.0";"93.0";"40.0";"3.9";"1.0";""
"RUSSELL";"RUSSELL";"USD";"1.0";"13.0";"2500.0";"38.0";"14.0";"1.35";"0.1";""
"SMI";"SMI";"CHF";"1.0";"50.0";"14000.0";"123.0";"52.0";"4.0";"3.0";""
"SPTRD";"SPTRD";"USD";"1.0";"7.0";"8000.0";"54.8";"24.5";"2.5";"0.4";""
"STXE";"STXE";"EUR";"1.0";"17.0";"6000.0";"71.0";"25.0";"2.5";"2.0";""
"USDCAD";"USDCAD";"CAD";"0.0001";"8.0";"15000.0";"54.0";"25.8";"1.6";"3.0";""
"""

NEWCURRENCIES="""NAME;FOREX;EUROS2
"CAD";"EUR/CAD";"1.64"
"CHF";"EUR/CHF";"0.93"
"EUR";"EURO";"1.0"
"GBP";"EUR/GBP";"0.87"
"HUF";"EUR/HUF";"387.7"
"JPY";"EUR/JPY";"173.11"
"MXN";"EUR/MXN";"21.58"
"SEK";"GBPSEK";"10.92"
"USD";"EUR/USD";"1.17"
"""

NEWTRADES="""TRADE;INSTRUMENT;SETUP;DATE;DIR;LOTS;TIMEIN;TIMEOUT;PTSIN;PTSOUT;SYSOUT;PTSSTOP;EUROS;EURSTOP;GRAF;NOTES;MISTAKES;WITH
"1";"IBEX";"ReboteH4";"2025-08-13";"Long";"2.0";"09:04";"09:26";"14915.0";"14963.0";"14980.0";"14882.0";"58.0";"-101.0";"/u/trade/diary/diarygraphs/trade1ibex.png";"ejemplo de trade";"";"1ra vela;Apertura;ApoyoH1;Apoyo4H"
"""
