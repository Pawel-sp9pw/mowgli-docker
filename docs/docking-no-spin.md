# Poprawka dokowania bez obrotu w miejscu

Dotyczy instalacji ARM64 z obrazu `ghcr.io/jeremysalwen/open_mower_ros:main`.
Obraz bazowy przypięto do manifestu
`sha256:8b3336582fa2351254632f3b904ba302f35eeca6ddd68c712e6d4d0605f5cd8e`.
Jego wariant ARM64 ma identyfikator konfiguracji
`sha256:46270817c3302d6d1e1d7786af247a5ca87141d0b853c30b1f9deecc315f2cfe`,
zgodny z odczytem z kosiarki. Wersja v2 zastępuje bibliotekę FTC i program
`mower_logic`, aby przełączyć oba etapy podejścia na osobny sterownik.

## Zachowanie

Końcowy wjazd nadal używa `DockingFTCPlanner`. Oba wcześniejsze etapy podejścia
używają teraz `DockingApproachFTCPlanner`, zarejestrowanego w obrazie.
Przy uruchomieniu nowy sterownik kopiuje rzeczywiste ustawienia `FTCPlanner`,
więc nie trzeba zastępować własnego pliku `custom_params.yaml`.
Przed startem nawigacji rejestracja dopisuje go do efektywnej listy sterowników,
także jeśli własny `custom_params.yaml` nadpisuje listę z obrazu. Pozostałe wpisy
są zachowane; konflikt nazwy nowego sterownika zatrzymuje start nawigacji.
Zwykły `FTCPlanner` podczas koszenia i wyjazd tyłem ze stacji zachowują
dotychczasowe działanie. Tryb jest wybierany ponownie dla każdego planu.

Wersja v1 nie obejmowała podejścia: obserwacja aktywnego
`/move_base_flex/FTCPlanner/global_point` przy około 20 Hz podczas postoju
potwierdziła, że w tamtej chwili pracował jeszcze poprzedni sterownik.

- W `WAITING_FOR_GOAL_APPROACH` robot może powoli nadrobić brakującą pozycję.
- Prędkość jest ograniczona do 0,1 m/s i istniejącego limitu sterownika.
- Prędkość obrotu nie przekracza `2 * prędkość liniowa`; przy zerowej jeździe
  obrót również wynosi zero. Robot nie wykonuje końcowego obrotu w miejscu.
- Błąd boczny ponad 0,1 m, błąd kierunku ponad 10 stopni, przekroczenie
  `max_follow_distance`, niepoprawne pomiary lub cofnięcie zegara przerywają próbę.
- Koniec końcowego wjazdu wymaga błędu pozycji poniżej 0,02 m albo mniejszej
  istniejącej tolerancji. Podejście zachowuje własną tolerancję pozycji, ponieważ
  nadal używa GPS. Po przekroczeniu `goal_timeout` w oczekiwaniu na pozycję
  sterownik zgłasza błąd zamiast sukcesu.
- Robot nie cofa podczas wjazdu i nie jedzie poza koniec zadanej trasy.
- Rozpoznawanie napięcia ładowania, anulowanie, GPS i zabezpieczenia odometrii
  pozostają obsługiwane przez dotychczasową logikę OpenMower.

Na zakrzywionym dojeździe do punktu ustawienia zachowane są początkowy obrót,
śledzenie trasy i potrzebne końcowe ustawienie kierunku poza prostym korytarzem.
W oczekiwaniu na pozycję także ten etap może nadrobić dystans i ma ograniczenie
obrotu zależne od jazdy. Przy przejściu do końcowego ustawienia kierunku wysyłane
jest zero, a kolejny cykl ocenia aktualny kąt celu przed wydaniem polecenia obrotu.
Jeżeli robot jest już ustawiony w wymaganej tolerancji, nie wykonuje korekty.

Nie zwiększaj `docking_distance`, tolerancji ani timeoutu w celu obejścia błędu.
Jeśli zapisany kierunek lub koniec trasy nie odpowiada stacji, trzeba poprawić
zapis punktu dokowania. Poprawka nie zastępuje tej kalibracji.

## Uruchomienie na kosiarce

Zatrzymaj zadanie w aplikacji i wykonuj polecenia na hoście, w katalogu repozytorium,
nie wewnątrz kontenera. Zachowaj własne `.env` i `mower_params/custom_params.yaml`;
nie zastępuj ich przykładowymi plikami z repozytorium.

Po pomyślnym zakończeniu workflow `Build docking no-spin fix`:

```bash
docker compose -f docker-compose.yaml -f docker-compose.docking.yaml pull openmower
docker compose -f docker-compose.yaml -f docker-compose.docking.yaml up -d --no-deps openmower
```

Dla odtwarzalnego wdrożenia ustaw `DOCKING_IMAGE` w `.env` na tag
`ghcr.io/pawel-sp9pw/mowgli-docker:docking-<pełny SHA zatwierdzenia>`
z pomyślnie zakończonego workflow. Alternatywnie zbuduj lokalnie:

```bash
docker compose -f docker-compose.yaml -f docker-compose.docking.yaml build openmower
docker compose -f docker-compose.yaml -f docker-compose.docking.yaml up -d --no-deps openmower
```

Sprawdź obraz i znacznik poprawki:

```bash
docker inspect mowgli-openmower --format '{{.Config.Image}}'
docker inspect mowgli-openmower --format '{{index .Config.Labels "io.mowgli.docking-fix"}}'
```

Znacznik powinien mieć wartość `no-spin-v2`. Przy pierwszej próbie obserwuj
dokowanie z wyłączonym nożem i możliwością natychmiastowego zatrzymania.
Sprawdź wjazd na styki, zatrzymanie po wykryciu ładowania oraz wyjazd tyłem.
Przy błędnym ustawieniu oczekiwanym zachowaniem jest przerwanie próby,
a nie obrót w miejscu. Kompilacja nie zastępuje tej próby sprzętowej.

Po aktualizacji sprawdź rejestrację sterownika:

```bash
docker exec mowgli-openmower bash -lc 'source /opt/ros/noetic/setup.bash; rosparam get /move_base_flex/controllers'
```

Lista musi zawierać `DockingApproachFTCPlanner`. Podczas podejścia publikowany
jest teraz `/move_base_flex/DockingApproachFTCPlanner/global_point`; podczas
końcowego wjazdu `/move_base_flex/DockingFTCPlanner/global_point`.
W logu pojawiają się komunikaty `Mowgli docking no-spin v2 initialized` oraz
`Mowgli docking v2 plan`, wskazujące wybrany tryb.

## Powrót do poprzedniego obrazu

Po zatrzymaniu zadania uruchom usługę bez pliku nakładki:

```bash
docker compose -f docker-compose.yaml up -d --no-deps --force-recreate openmower
```

Wtedy ponownie używany jest dotychczasowy `IMAGE` z `.env`.
