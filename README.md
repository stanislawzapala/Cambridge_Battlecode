# Cambridge_Battlecode
Cambridge Battlecode challenge

## Instalacja pakietu cambc
pip install cambc
UWAGA - potrzeba połączenia z rustem (ja musiałem zainstalować visual studio (to zwykłe, nie code!) z opcją deskapp development with c++ czy coś takiego).
Druga rzecz - pakiet leci na wersji pythona 3.12 / 3.13. Na nowszych wyskakuje błąd.



## Pomysły
1. markerynr 1 - do zapisywania lokalnie pewnej drogi do bazy? taki roadmap, albo stawianie ich co jakiś czas
2. markery nr 2: 
32-Bitowy Protokół Roju
Wiadomość (2 bity): Bity 30-31 (od 0 do 3). 0 = MAP_UPDATE.
Tura (11 bitów): Bity 19-29 (od 0 do 2047).
X (6 bitów): Bity 13-18 (od 0 do 63).
Y (6 bitów): Bity 7-12 (od 0 do 63).
Teren (2 bity): Bity 5-6 (0=EMPTY, 1=WALL, itd.).
Budynek (4 bity): Bity 1-4 (0=Brak, 1=CORE, itd.).
Drużyna (1 bit): Bit 0 (0=My, 1=Wróg).


## Podpatrzone taktyki:
1. Defensywa - postawienie splitterów poza rogami i środkami boków, a w pozostałych miejscach wieżyczki - (gościu stawiał sentinele, ale może lepiej gunnery?)
2. cannon rush
3. bunkier na mapie po stronie przeciwnika



