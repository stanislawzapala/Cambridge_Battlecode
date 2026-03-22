# Cambridge_Battlecode
Cambridge Battlecode challenge

# Projekt PUDEL - Dziennik Zmian (Changelog)

## Aktualna Wersja
**v9: Stable (Fuzja)**
- Połączenie pełnej Maszyny Stanów (v7) z systemami omijania blokad (v8). Boty poprawnie rozdzielają role (Zwiadowca / Budowniczy), pamiętają mapę i inteligentnie omijają przeszkody bez wpadania w nieskończone pętle.

---

## To do list
- pozamieniać self.słowniki na self.wartości. np self.bots_id. bo obecnie jest tak, jakby miały współdzieloną pamięć
- obecnie markery spamią się z dowolną informacją o wrogiej strukturze - czyli też o drodze. a wolelibyśmy priorytetyzować informacje o ważniejszych budynkach lub o złożach.
- Brak bezpośredniego ataku na Core wroga
Strategia skupia się wyłącznie na ekonomii i defensywie. Żaden bot nigdy nie idzie w stronę wrogiego Core — nawet gdy jest znany z VIP Facts. Można by dodać typ bota (np. jako 5. w rotacji po turze 400, albo jako upgrade KAMIKAZE gdy brak wrogich Harvesterów) który próbuje dotrzeć do Core wroga i dokonuje autodestrukcji na nim lub jego bezpośrednim otoczeniu. Nawet 20 DMG z jednego bota skumulowane przez kilka takich ataków może być istotne pod koniec gry.
- KAMIKAZE nie przejmuje złoża po ataku
Po postawieniu Sentinela KAMIKAZE od razu staje się REPAIRMAN — bez czekania na zniszczenie Harvestera i bez próby przejęcia złoża. Brakuje logiki oblężenia: postaw drogę na złożu jako blokadę → poczekaj → zbuduj nasz Harvester. To zwłaszcza boli, bo Sentinel jest już na miejscu i prawie na pewno zniszczy Harvestera — a złoże zostaje niezagospodarowane.
- Smelter niszczy infrastrukturę bez sprawdzenia surowców przy podłączaniu
W fazie connect, gdy src_pos.distance_squared(fpos) <= 9, Smelter po prostu robi ct.destroy(src_pos) i próbuje postawić Most. Jeśli Most się nie uda (brak surowców), element sieci jest trwale zniszczony. Brak analogicznej do fazy build ochrony "destroy tylko gdy stać".
- FORTIFIER nie ma trybu oblężenia przy wrogich Harvesterach
Gdy Fortifier wyczerpie miejsca na Sentinele przy wrogim Harvesterze, po prostu szuka nowego celu. Tymczasem Sentinele które właśnie postawił prawie na pewno zniszczą Harvestera — i złoże zostaje puste, gotowe do przejęcia przez wroga lub przez nas. Brak mechanizmu czekania i budowy własnego Harvestera na uwolnionym złożu.
- Smelter nie monitoruje Foundry po zakończeniu budowy
Po fazie fortify Smelter zostaje REPAIRMAN i nigdy więcej nie wraca do Foundry. Jeśli Foundry zostanie zniszczone lub odcięte od surowców (np. wróg przerwie Conveyor wejściowy), nikt tego nie zauważy i nie odbuduje. Brakuje fazy watch — ciągłego monitorowania przez jednego dedykowanego Smeltera.
- Brak koordynacji przy wielu botach ciągnących do tego samego Splittera
Gdy kilka botów jednocześnie jest w BUILD_BELT i każdy celuje w ten sam Splitter, mogą wzajemnie nadpisywać sobie Conveyory lub budować równoległe, niepotrzebne nitki do jednego punktu. Mechanizm rezerwacji (kanał 1) działa tylko dla złóż — nie dla punktów docelowych sieci. Splitter który już jest zasilany mógłby być oznaczony jako "zajęty" przez marker, żeby kolejne boty szukały innego wejścia.
- Brak użycia Armoured Conveyor i Barrier
ARMOURED_CONVEYOR (odporny na uszkodzenia) i BARRIER (czysto defensywny) są zdefiniowane w kodzie ale nigdy nie są budowane. Odcinki sieci blisko linii frontu (np. w pobliżu wrogich Sentineli lub Gunnerów) mogłyby być budowane z Armoured Conveyor zamiast zwykłego — szczególnie gdy Repairman wykryje ciągłe uszkodzenia w tym samym miejscu.


## Podpatrzone taktyki:
0. (!!!) Produkcja probek, któe stoją na kluczowych dla nas mostach!
1. Defensywa - postawienie splitterów poza rogami i środkami boków, a w pozostałych miejscach wieżyczki - (gościu stawiał sentinele, ale może lepiej gunnery?)
2. cannon rush
3. bunkier na mapie po stronie przeciwnika
4. swarm botów stojących wokół bazy przeciwnika blokujących ruchy
5. szybkie zajmowanie wszystkich pól wokół złóż własną drogą
6. niszczenie harvesterów wroga taktyką gunner + conveyor


## Historia Wersji (Archiwum)

* **v8: Anti-Deadlock** 
  - Poprawki błędów zacinania się botów (Infinite State Loop).
  - Dodanie "Czarnej Listy" nieosiągalnych celów.

* **v7: State Engine (FSM)** 
  - Wprowadzenie Maszyny Stanów (Finite State Machine).
  - Boty zyskały "Mózg" i potrafią zmieniać role (EXPLORE, SCOUT, BUILD_MINE, BUILD_BELT).
  - Implementacja Partial A* (zatrzymywanie się obok celu i omijanie ogromnych przeszkód).
  - Ignorowanie markerów na złożach podczas budowy.
  - Poprawienie elementów listy VIP - wyrzucenie z niej dróg i conveyorów wroga. Teraz rzeczywiście vip.

* **v6: Core Scan** 
  - Rdzeń (Core) przy starcie skanuje otoczenie i wysyła pierwsze feromony, dając botom początkową wiedzę o mapie ("Protokół Rozruchowy").

* **v5: Feromony (Komunikacja)**  
  - Wdrożenie systemu komunikacji między botami ("Gossip Protocol"). Boty zapisują odkrycia w koderze markerów i czytają znaczniki innych botów, tworząc współdzieloną Listę VIP (POI).

* **v4: Pamięć (Memory)** 
  - Boty zyskały indywidualną pamięć topograficzną (ściany, rudy) oraz pamięć dynamiczną z timestampami (budynki, sojusznicy, wrogowie).

* **v3: Ruch Hybrydowy** 
  - Optymalizacja zużycia procesora: boty idą prosto do celu ("Zachłanny Insekt"), a algorytmu A* używają tylko w sytuacjach awaryjnych (uderzenie w przeszkodę).

* **v1-v2: Nawigacja A*** 
  - Podstawy ruchu oparte na algorytmie A-Star i jego wstępne optymalizacje. 








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







