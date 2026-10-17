# Poprawka dokowania bez obrotu w miejscu

Dotyczy instalacji ARM64 z obrazu `ghcr.io/jeremysalwen/open_mower_ros:main`.
Obraz bazowy przypięto do manifestu
`sha256:8b3336582fa2351254632f3b904ba302f35eeca6ddd68c712e6d4d0605f5cd8e`.
Jego wariant ARM64 ma identyfikator konfiguracji
`sha256:46270817c3302d6d1e1d7786af247a5ca87141d0b853c30b1f9deecc315f2cfe`,
zgodny z odczytem z kosiarki. Wersja v6 zastępuje bibliotekę FTC, program
`mower_logic` oraz `xbot_positioning`. Nie zmienia map ani parametrów sprzętu.

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
Wersja v3 poprawia przekazanie pozycji pomiędzy etapami: v2 stosowała zbyt wcześnie
sztywne limity końcowego wjazdu (0,1 m i 10 stopni), mimo że wcześniejszy dojazd
mógł poprawnie zakończyć się z tolerancją 0,2 m i 20 stopni.

Wersja v4 usuwa dwie przyczyny kolejnych przerwań widocznych w logach v3:
punkt prowadzący poruszał się z prędkością 0,3/0,15 m/s, mimo ograniczenia robota
do 0,1 m/s, więc wyprzedzał go o ponad `max_follow_distance=0.55`.
Ponadto tolerancje pozycji i kierunku celu były błędnie użyte jako granice
śledzenia całego podejścia. Błąd boczny 0,206758 m przerywał próbę przy tolerancji
celu 0,2 m, mimo że mieścił się w promieniu śledzenia 0,55 m.

- W `WAITING_FOR_GOAL_APPROACH` robot może powoli nadrobić brakującą pozycję.
- Prędkość jest ograniczona do 0,1 m/s i istniejącego limitu sterownika.
- Na prostych odcinkach taki sam limit obowiązuje punkt prowadzący oraz jego
  prędkość początkową, przed uwzględnieniem mnożnika ograniczenia prędkości.
  Nie zwiększamy `max_follow_distance` w celu zamaskowania opóźnienia robota.
- Prędkość obrotu nie przekracza `2 * prędkość liniowa`; przy zerowej jeździe
  obrót również wynosi zero. Robot nie wykonuje końcowego obrotu w miejscu.
- Podczas końcowego wjazdu błąd boczny ponad 0,1 m lub błąd kierunku ponad
  10 stopni przerywa próbę. Podczas prostego podejścia obowiązują promień
  `max_follow_distance` oraz osobny limit kierunku 45 stopni, umożliwiający
  korektę boczną podczas jazdy. Tolerancje celu dotyczą zakończenia podejścia,
  nie każdego punktu prowadzącego. W obu etapach przekroczenie `max_follow_distance`,
  niepoprawne pomiary lub cofnięcie zegara przerywają próbę.
- Koniec końcowego wjazdu wymaga błędu pozycji poniżej 0,02 m albo mniejszej
  istniejącej tolerancji. Proste podejście przed przekazaniem do końcowego wjazdu
  wymaga błędu pozycji poniżej 0,1 m i kierunku poniżej 10 stopni, albo mniejszych
  skonfigurowanych tolerancji. Błąd mieszczący się w szerszej tolerancji dojazdu
  jest korygowany podczas ruchu zamiast natychmiast przerywać próbę.
  Po przekroczeniu `goal_timeout` w oczekiwaniu na pozycję sterownik zgłasza błąd.
- Robot nie cofa podczas wjazdu i nie jedzie poza koniec zadanej trasy.
- Rozpoznawanie napięcia ładowania, anulowanie, GPS i zabezpieczenia odometrii
  pozostają obsługiwane przez dotychczasową logikę OpenMower.

Na zakrzywionym dojeździe do punktu ustawienia zachowane są początkowy obrót,
śledzenie trasy i potrzebne końcowe ustawienie kierunku poza prostym korytarzem.
W oczekiwaniu na pozycję także ten etap może nadrobić dystans i ma ograniczenie
obrotu zależne od jazdy. Przy przejściu do końcowego ustawienia kierunku wysyłane
jest zero, a kolejny cykl ocenia aktualny kąt celu przed wydaniem polecenia obrotu.
Jeżeli robot jest już ustawiony w wymaganej tolerancji, nie wykonuje korekty.

Trasa podejścia jest publikowana także pod dotychczasowym
`/move_base_flex/FTCPlanner/global_plan`, używanym przez starszy podgląd trasy.
Oba sterowniki korzystają z tego samego zatrzaskiwanego wydawcy, aby po ponownym
połączeniu podgląd nie wybierał pomiędzy dwiema nieaktualnymi kopiami trasy.
Tematy `global_point` pozostają oddzielne i wskazują rzeczywiście aktywny sterownik.
Komunikaty `Mowgli docking v6 limit` zawierają etap, błędy i obowiązujące limity.

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

Znacznik powinien mieć wartość `no-spin-v6`. Przy pierwszej próbie obserwuj
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
W logu pojawiają się komunikaty `Mowgli docking no-spin v6 initialized` oraz
`Mowgli docking v6 plan`, wskazujące wybrany tryb.

## Korekta blokady kierunku w v5

Na urządzeniu potwierdzono rzeczywisty pomiar ruchu z
`/xbot_positioning/wheel_ticks_in`, około 47,5 Hz także na postoju.
`wheel_tick_factor=330`, `valid_wheels=12` i kolejne znaczniki czasu co 21 ms
są poprawne; niezmienne liczniki tylnych kół potwierdzają postój w tej próbce.
Brak publikacji `/ll/diff_drive/measured_twist` jest w tej instalacji normalny:
już v4 odświeżała pomiar prędkości również z enkoderów. Nie trzeba dodawać
przekierowania, a `/cmd_vel` nie jest pomiarem ruchu.

W v4 każdy niepoprawny odstęp IMU usuwał zapis i unieważniał kierunek, także
pojedynczy duplikat. Powrót dobrych danych nie przywracał ważności. Ponadto
inicjalizacja z ładującej stacji w IDLE mogła wykonać się tylko raz na wejście
do tego stanu. To powodowało blokadę również po kolejnej utracie kierunku.
Najnowsze pomiary nie odtwarzają wcześniejszego zdarzenia: samo stare ostrzeżenie
nie pozwala ustalić, czy nastąpił duplikat, cofnięcie czasu czy długa przerwa.

W v5:

- Pojedyncze duplikaty i lekko spóźnione próbki IMU/enkoderów są odrzucane,
  bez cofania ostatniego poprawnego znacznika czasu, podwójnej integracji ani
  dzielenia przez zero. Nie kasują znanego kierunku.
- Trzecia kolejna próbka bez postępu czasu, przerwa ponad 0,5 s, cofnięcie
  czasu o ponad 0,5 s lub niepoprawne wartości nadal unieważniają kierunek.
  Świeże pomiary po rzeczywistej utracie danych nie uprawniają do jazdy
  z nieznanym kierunkiem. Wymagana jest ponowna inicjalizacja.
- Enkodery wymagają niezerowego przelicznika i obu ważnych tylnych kół.
  Ruch któregokolwiek tylnego koła usuwa zapis postoju również wtedy, gdy
  przeciwne obroty dają zerową średnią prędkość liniową.
- W stanie IDLE, przy świeżym napięciu ładowania i nieważnym kierunku, ustawienie
  pozycji ze stacji może być ponowione, nie częściej niż co 2 s. Nie ma takiej
  automatycznej inicjalizacji poza stacją.
- Komunikaty `dropped IMU sample`, `IMU discontinuity`, `dropped wheel sample`
  i `invalid wheel sample` podają rzeczywiste `dt`. `seq: 0` nie jest kryterium
  błędu; oceniane są znaczniki czasu, nie numer sekwencji.

Po przejściu z v4 z `orientation_valid=0` zatrzymaj zadanie i ustaw robot
prawidłowo w ładującej stacji. Oczekuj komunikatu
`Mowgli heading v5: initialized heading from the charging dock.`
Następnie sprawdź `orientation_valid` po nadejściu świeżych danych IMU.
Ta aktualizacja nie naprawia błędów sieci i sum kontrolnych transmisji.

## Zapis postoju niezależny od wyłączenia GPS w IDLE — v6

Po restarcie użytkownik otrzymał `checkpoint=0`, `BRAK ZAPISU` i
`orientation_valid=0`. Nie nastąpiło więc odtworzenie błędnego zapisanego kąta:
brakowało danych do odtworzenia. Wcześniej zarejestrowano rzeczywistą
nieciągłość czasu IMU `dt=4.24175`, po której kierunek został zainicjalizowany
w stacji. V6 nie zwiększa limitu IMU, aby ukryć tę nieciągłość.

W v5 zapis wymagał `has_gps` i aktualnego `last_gps_time` z filtra pozycji.
Tymczasem IDLE celowo wyłącza aktualizacje GPS, a zatrzymanie/przerwanie
oddokowania może nastąpić przed zakończeniem oczekiwania na GPS.
W takim stanie sam postój nie wystarczał do utworzenia pliku.

V6 obserwuje `/ll/position/gps` przed sprawdzeniem przełącznika filtra:

- Do zapisu wymagane jest 10 kolejnych, różnych w czasie pomiarów RTK Fixed
  spełniających istniejący limit dokładności. Niepoprawne lub nieaktualne dane
  resetują walidację; duplikaty nie zwiększają licznika. Skok pozycji ponad
  0,25 m lub przerwa pomiarów ponad 1 s rozpoczynają walidację od nowa.
- Nadal wymagany jest wcześniej znany kierunek, co najmniej 2 s postoju,
  świeże pomiary prędkości i IMU oraz skalibrowany żyroskop. Dobry RTK nie
  dostarcza kierunku nieruchomego robota i nie zastępuje jego inicjalizacji.
- Zapis zawiera aktualną zmierzoną pozycję anteny i znany kierunek filtra,
  nie potencjalnie nieaktualną pozycję niekorygowanej odometrii.
- Obserwacja nie włącza GPS w filtrze ani nie zmienia bieżącego stanu filtra.
  Dotychczasowe zachowanie IDLE i oddokowania pozostaje zachowane.
- Pierwszy udany zapis po zatrzymaniu jest komunikatem WARN z pełną ścieżką
  pliku: `Mowgli heading v6: stationary heading checkpoint saved; file=...`.
  Jeśli zabraknie świeżego RTK lub IMU, log `checkpoint not saved` podaje
  licznik próbek i ich wiek. Nie restartuj przed potwierdzeniem udanego zapisu.

Po aktualizacji rozpocznij od prawidłowo ustawionej, ładującej stacji:
utraconego wcześniej zapisu nie można odtworzyć z samego obrazu mapy.
Po oddokowaniu zatrzymaj robot i poczekaj na komunikat udanego zapisu.
Następnie, bez przestawiania i obracania robota, sprawdź restart.
Oczekiwane komunikaty to `checkpoint=1` i
`Mowgli heading v6 restored after stationary GPS validation`.
Potwierdź także `orientation_valid=1` oraz fizyczną zgodność kierunku.

## Kierunek po restarcie poza stacją

Oryginalny filtr pozycji zaczyna od `(0, 0, 0)` i oznacza kierunek jako poprawny,
choć nieruchomy odbiornik GPS nie zna kierunku przodu robota. Poza stacją
zapisany kierunek stacji nie jest automatycznie przywracany. Dlatego poprawka
nie dodaje stałego obrotu o 180 stopni: taki obrót zepsułby poprawnie ustaloną
orientację w innych miejscach.

Użytkownik potwierdził, że podczas wyłączenia robot nie jest przestawiany ani
obracany. Przy tym założeniu v6 zachowuje znany kierunek podczas postoju:

- Kierunek musi najpierw zostać zainicjalizowany z pozycji stacji lub przez
  istniejącą usługę ustawienia pozycji. Dowolne początkowe zero nie jest zapisywane
  jako kierunek wiarygodny. Przy wykryciu świeżego napięcia ładowania w stanie
  IDLE kierunek może być zainicjalizowany z zapisanego punktu stacji bez wyjazdu.
- Po co najmniej 2 sekundach postoju, ze świeżym surowym RTK i znanym kierunkiem,
  zapisywany jest plik `$ROS_HOME/mowgli-heading-v1.txt` albo
  `~/.ros/mowgli-heading-v1.txt`. Istniejący montowany katalog `./ros` zachowuje go
  po odtworzeniu kontenera. Zapis odbywa się przez plik tymczasowy i zmianę nazwy.
- Wykrycie ruchu usuwa poprzedni punkt postoju, aby restart w trakcie jazdy nie
  odtworzył kierunku sprzed przejazdu. Po zatrzymaniu powstaje nowy zapis.
  Zanik wcześniej dostępnych danych prędkości również unieważnia zapis, a ruch
  obrotowy jest sprawdzany niezależnie od dostępności prędkości liniowej.
  Jawne ustawienie pozycji usuwa poprzedni zapis kierunku.
- Po restarcie przywrócenie wymaga zapisu nie starszego niż 24 godziny, zgodnych
  przesunięć anteny, postoju, świeżych danych prędkości i IMU, kalibracji żyroskopu
  oraz 10 kolejnych świeżych pomiarów RTK Fixed, w promieniu 0,25 m od zapisanej
  pozycji anteny. Aktualna pozycja jest przeliczana z uwzględnieniem przesunięcia
  anteny. Nie jest przywracana dawna pozycja GPS.
- Bez wiarygodnego zapisu lub przy odrzuceniu przywrócenia kierunek pozostaje
  nieważny dla kontroli GPS. Wtedy wymagane jest ponowne ustawienie pozycji,
  zamiast jazdy autonomicznej z arbitralnym kierunkiem zero.

Przy pomijaniu kalibracji żyroskopu pierwszy znacznik czasu IMU jest teraz
inicjalizowany przed prognozą filtra. Niepoprawne odstępy nie są całkowane;
rozróżnienie duplikatów i rzeczywistej utraty danych opisano w sekcji v5.
Nie wolno zapisywać ani przywracać kierunku po nieobserwowanym ruchu.

Pierwsze uruchomienie v6 wykonaj w prawidłowo ustawionej stacji. Po normalnym
wyjeździe i odzyskaniu RTK zatrzymaj zadanie, poczekaj kilka sekund i sprawdź
komunikat `Mowgli heading v6: stationary heading checkpoint saved; file=...`.
Dopiero potem sprawdzaj restart poza stacją. Pomyślne przywrócenie potwierdza
`Mowgli heading v6 restored after stationary GPS validation`.
Próby wykonuj z wyłączonym nożem i możliwością natychmiastowego zatrzymania.

GPS nie wykryje ręcznego obrócenia robota w tym samym miejscu podczas wyłączenia.
Jeżeli zostanie przestawiony, usuń zapis postoju i zainicjalizuj pozycję ponownie
w stacji. Nie używaj tego mechanizmu bez założenia nieruchomości po wyłączeniu.
Ustawienie `xbot_positioning/mowgli_restore_stationary_heading: false` we własnych
parametrach przywraca poprzednią inicjalizację filtra; nie jest rozwiązaniem
problemu nieznanego kierunku poza stacją.

## Granice weryfikacji

Sprawdzenia przed publikacją obejmują kompilację ARM64 i wiązanie bibliotek,
testy C++ polityki ograniczeń oraz symulację regulatorów przy 20 Hz, z wartościami
podanymi przez użytkownika. Model odtwarza błąd v3 i sprawdza dojście v4 do
punktu przekazania, także z odchyleniami bocznymi z logów. Testy kierunku obejmują
zapis, odczyt, przywrócenie oraz odrzucanie ruchu i niepoprawnych pomiarów.
Dla v5 lokalne testy C++ wykonują także fragment obsługi IMU i pełny callback
enkoderów wygenerowane przez ten sam skrypt, który modyfikuje obraz bazowy.
Sprawdzane są duplikaty, opóźnione próbki, powtarzające się błędy czasu, realne
przerwy, niepoprawny przelicznik, maska kół oraz dane postoju z urządzenia.
Dla v6 dodano scenariusz wyłączonego filtra GPS po oddokowaniu: zapis, odczyt
i przywrócenie tego samego kierunku po symulowanym restarcie. Testy sprawdzają
także odrzucanie nieznanego kierunku, nieaktualnych danych, duplikatów i utraty RTK.
Nie zastępuje to weryfikacji fizycznego robota, przyczepności ani jakości GPS.

Błędy `Network is unreachable` i niezgodne sumy kontrolne są osobnymi problemami
łączności. Ta poprawka ich nie maskuje ani nie zmniejsza wymagań świeżości danych.

## Powrót do poprzedniego obrazu

Po zatrzymaniu zadania uruchom usługę bez pliku nakładki:

```bash
docker compose -f docker-compose.yaml up -d --no-deps --force-recreate openmower
```

Wtedy ponownie używany jest dotychczasowy `IMAGE` z `.env`.
