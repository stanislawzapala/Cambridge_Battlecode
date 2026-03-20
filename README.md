# Cambridge_Battlecode
Cambridge Battlecode challenge

# Projekt PUDEL - Dziennik Zmian (Changelog)

## Aktualna Wersja
**v9: Stable (Fuzja)**
- Połączenie pełnej Maszyny Stanów (v7) z systemami omijania blokad (v8). Boty poprawnie rozdzielają role (Zwiadowca / Budowniczy), pamiętają mapę i inteligentnie omijają przeszkody bez wpadania w nieskończone pętle.

---

## Historia Wersji (Archiwum)

* **v8: Anti-Deadlock** - Poprawki błędów zacinania się botów (Infinite State Loop).
  - Dodanie "Czarnej Listy" nieosiągalnych celów.

* **v7: State Engine (FSM)** - Wprowadzenie Maszyny Stanów (Finite State Machine).
  - Boty zyskały "Mózg" i potrafią zmieniać role (EXPLORE, SCOUT, BUILD_MINE, BUILD_BELT).
  - Implementacja Partial A* (zatrzymywanie się obok celu i omijanie ogromnych przeszkód).
  - Ignorowanie markerów na złożach podczas budowy.

* **v6: Core Scan** - Rdzeń (Core) przy starcie skanuje otoczenie i wysyła pierwsze feromony, dając botom początkową wiedzę o mapie ("Protokół Rozruchowy").

* **v5: Feromony (Komunikacja)** - Wdrożenie systemu komunikacji między botami ("Gossip Protocol").
  - Boty zapisują odkrycia w koderze markerów i czytają znaczniki innych botów, tworząc współdzieloną Listę VIP (POI).

* **v4: Pamięć (Memory)** - Boty zyskały indywidualną pamięć topograficzną (ściany, rudy) oraz pamięć dynamiczną z timestampami (budynki, sojusznicy, wrogowie).

* **v3: Ruch Hybrydowy** - Optymalizacja zużycia procesora: boty idą prosto do celu ("Zachłanny Insekt"), a algorytmu A* używają tylko w sytuacjach awaryjnych (uderzenie w przeszkodę).

* **v1-v2: Nawigacja A*** - Podstawy ruchu oparte na algorytmie A-Star i jego wstępne optymalizacje. 








## Instalacja pakietu cambc
pip install cambc
UWAGA - potrzeba połączenia z rustem (ja musiałem zainstalować visual studio (to zwykłe, nie code!) z opcją deskapp development with c++ czy coś takiego).
Druga rzecz - pakiet leci na wersji pythona 3.12 / 3.13. Na nowszych wyskakuje błąd.


## To do list
- obecnie markery spamią się z dowolną informacją o wrogiej strukturze - czyli też o drodze. a wolelibyśmy priorytetyzować informacje o ważniejszych budynkach lub o złożach.


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




