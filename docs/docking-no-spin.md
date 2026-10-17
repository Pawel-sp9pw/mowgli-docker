# Poprawka dokowania bez obrotu w miejscu

Dotyczy instalacji ARM64 z obrazu `ghcr.io/jeremysalwen/open_mower_ros:main`.
Obraz bazowy przypięto do manifestu
`sha256:8b3336582fa2351254632f3b904ba302f35eeca6ddd68c712e6d4d0605f5cd8e`.
Jego wariant ARM64 ma identyfikator konfiguracji
`sha256:46270817c3302d6d1e1d7786af247a5ca87141d0b853c30b1f9deecc315f2cfe`,
zgodny z odczytem z kosiarki. Poprawka zastępuje tylko bibliotekę FTC.

## Zachowanie

Zmiana działa wyłącznie w `DockingFTCPlanner`, dla prostych tras do przodu.
Zwykły `FTCPlanner` i wyjazd tyłem ze stacji zachowują dotychczasowe działanie.
Tryb jest wybierany ponownie dla każdego planu, także po ponowieniu dokowania.

- W `WAITING_FOR_GOAL_APPROACH` robot może powoli nadrobić brakującą pozycję.
- Prędkość jest ograniczona do 0,1 m/s i istniejącego limitu sterownika.
- Prędkość obrotu nie przekracza `2 * prędkość liniowa`; przy zerowej jeździe
  obrót również wynosi zero. Robot nie wykonuje końcowego obrotu w miejscu.
- Błąd boczny ponad 0,1 m, błąd kierunku ponad 10 stopni, przekroczenie
  `max_follow_distance`, niepoprawne pomiary lub cofnięcie zegara przerywają próbę.
- Koniec trasy wymaga błędu pozycji poniżej 0,02 m albo mniejszej istniejącej
  tolerancji. Po przekroczeniu `goal_timeout` sterownik zgłasza błąd zamiast sukcesu.
- Robot nie cofa podczas wjazdu i nie jedzie poza koniec zadanej trasy.
- Rozpoznawanie napięcia ładowania, anulowanie, GPS i zabezpieczenia odometrii
  pozostają obsługiwane przez dotychczasową logikę OpenMower.

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

Znacznik powinien mieć wartość `no-spin-v1`. Przy pierwszej próbie obserwuj
dokowanie z wyłączonym nożem i możliwością natychmiastowego zatrzymania.
Sprawdź wjazd na styki, zatrzymanie po wykryciu ładowania oraz wyjazd tyłem.
Przy błędnym ustawieniu oczekiwanym zachowaniem jest przerwanie próby,
a nie obrót w miejscu. Kompilacja nie zastępuje tej próby sprzętowej.

## Powrót do poprzedniego obrazu

Po zatrzymaniu zadania uruchom usługę bez pliku nakładki:

```bash
docker compose -f docker-compose.yaml up -d --no-deps --force-recreate openmower
```

Wtedy ponownie używany jest dotychczasowy `IMAGE` z `.env`.
