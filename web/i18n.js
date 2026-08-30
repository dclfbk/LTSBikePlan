// Translations for web/index.html - one object per language, same key set
// throughout. `rules` mirrors code/ltsbikeplan/assets/LTS_decisionrule_dict.json's
// rule_message_dict by rule code (already exported per edge as `rule`), so
// the "Motivazione LTS"/"LTS rationale" sentence can be shown in whichever
// language is selected instead of only the Italian baked into the export at
// compute-lts time.
const I18N = {
  it: {
    legendToggle: "Legenda",
    legendHint: "Clicca per mostrare/nascondere",
    legendZoomDisabledHint: "Visibile da zoom {zoom} in poi",
    bgLight: "Sfondo chiaro",
    bgSummer: "Sfondo estivo",
    bgCycling: "Sfondo ciclabile",
    bgDark: "Sfondo scuro",
    terrainToggle: "Terreno 3D",
    printControl: "Stampa mappa",
    shareButton: "Condividi",
    shareCopied: "Copiato!",
    shareModalHeading: "Condividi questa vista",
    shareUrlLabel: "Link",
    shareCopyButton: "Copia",
    shareEmbedLabel: "Codice da incorporare (iframe)",
    shareSocialLabel: "Condividi sui social",
    shareIntentText: "Visita Stress In Bici per conoscere la ciclabilità delle strade italiane",
    shareMastodonInstancePrompt: "Il nome del tuo server Mastodon (es. mastodon.social)",
    pdfCenterLabel: "Centro",
    pdfScaleLabel: "Scala",
    geocoderPlaceholder: "Cerca un luogo...",
    routingToggle: "Percorso",
    routingStartLabel: "Partenza",
    routingEndLabel: "Arrivo",
    routingClickHint: "Clicca sulla mappa<br>per impostare partenza e arrivo",
    routingDisclaimerSummary: "Come funziona questo calcolo",
    routingDisclaimerBody: "Il percorso privilegia i tratti con livello di stress (LTS) più basso e non considera i tratti classificati come non ciclabili: se l'unico collegamento verso una destinazione passa da lì, il percorso potrebbe non essere calcolabile. Non tiene conto del traffico in tempo reale, perché non è un dato disponibile. È un motore sperimentale ed elabora il percorso localmente, sul tuo dispositivo. Il tempo stimato è calcolato sia per una bicicletta muscolare che per una elettrica, e tiene conto della pendenza reale del terreno, ma non di vento, forma fisica o soste.",
    routingBikeMuscularLabel: "Bici muscolare",
    routingBikeElectricLabel: "Bici elettrica",
    routeEstimatedTimeTemplate: (h, m) => (h > 0 ? `~${h} h ${m} min` : `~${m} min`),
    routingClearButton: "Cancella",
    routingCalculating: "Calcolo del percorso...",
    routingNoRoute: "Nessun percorso trovato: partenza e arrivo non risultano ancora collegati da strade a basso stress mappate.",
    routingPartialRouteTemplate: (km) => `Percorso parziale: oltre questo punto (segnalato in arancione) la strada non è ciclabile. La destinazione dista ancora circa ${km} km.`,
    routingNoCoverage: "Instradamento non ancora disponibile in questa zona.",
    routeKmSoFar: "Km percorsi",
    routeTotalKm: "Lunghezza totale",
    routeElevationHeading: "Profilo altimetrico",
    routeLtsSegmentTemplate: (km, pct, descriptor) => `${km}km (${pct}%) di percorso ${descriptor}`,
    routeFacilitySegmentTemplate: (km, pct, label) => `${km}km (${pct}%) di ${label}`,
    routeDownloadHeading: "Scarica il percorso",
    routeDownloadGeoJson: "GeoJSON",
    routeDownloadGpx: "GPX",
    routeDownloadKml: "KML",
    loadingTitle: "Caricamento...",
    zoomHint: "Aumenta lo zoom per vedere le strade",
    zoomClickHint: "Aumenta ancora lo zoom per cliccare una strada",
    facilityStreet: "Strada",
    facilityCycleway: "Pista ciclabile",
    facilityPath: "Sentiero / sterrato",
    gapToggle: "Tratti da valutare",
    aboutToggle: "Info sul progetto",
    faqToggle: "FAQ",
    faqHeading: "FAQ",
    faqCloseAndScrollUp: "Chiudi e torna su",
    aboutHeading: "Stress in bici",
    aboutSubtitle: "Quanto stress può generare una strada quando la percorri in bici?",
    aboutBody: `<p><strong>Stress in bici</strong> è una mappa delle strade italiane vista dalla prospettiva delle persone che si muovono in bicicletta.</p>
<p>L'idea è semplice: le caratteristiche di una strada possono cambiare molto la nostra esperienza in bici. Traffico, velocità, corsie, parcheggi e infrastrutture ciclabili possono farci sentire più a nostro agio oppure aumentare pressione e disagio durante il percorso.</p>
<p>In letteratura scientifica esiste un indicatore chiamato <a href="https://peterfurth.sites.northeastern.edu/level-of-traffic-stress/" target="_blank" rel="noopener"><strong>LTS - Level of Traffic Stress</strong></a>.</p>
<p>L'LTS <a href="https://peterfurth.sites.northeastern.edu/2014/05/21/criteria-for-level-of-traffic-stress/" target="_blank" rel="noopener">classifica</a> le strade in base al livello di stress che le loro caratteristiche possono generare nelle persone che le percorrono in bicicletta.</p>
<h3>Come funziona</h3>
<p>Ogni tratto di strada riceve un valore di <strong>LTS da 1 a 4</strong>:</p>
<ul>
<li><strong>LTS 1</strong> - stress molto basso</li>
<li><strong>LTS 2</strong> - stress basso</li>
<li><strong>LTS 3</strong> - stress elevato</li>
<li><strong>LTS 4</strong> - stress molto elevato</li>
</ul>
<p>Il calcolo considera elementi concreti come il tipo di strada, la presenza di piste o corsie ciclabili, i limiti di velocità, il numero di corsie, i parcheggi e la larghezza della carreggiata.</p>
<p>L'LTS <strong>non è un indice di incidentalità</strong>. Prova a raccontare un'altra cosa: <strong>come le caratteristiche della strada possono influire sulla percezione di chi la percorre in bici</strong>.</p>
<h3>Anche la pendenza conta</h3>
<p>Nel nostro adattamento dell'LTS abbiamo aggiunto anche la <strong>pendenza</strong>.</p>
<p>Una strada può essere ben separata dalle auto, ma una salita lunga e ripida può comunque cambiare molto l'esperienza di chi la percorre.</p>
<p>Quando una salita è sufficientemente lunga e ripida, il valore LTS può aumentare.</p>
<p>Nella mappa è disponibile anche una vista tridimensionale, che permette di leggere meglio questa caratteristica.</p>
<h3>Tratti da valutare</h3>
<p>Non tutte le strade hanno lo stesso ruolo nella rete.</p>
<p>A volte basta un breve tratto ad alto stress per interrompere il collegamento tra zone dove, per il resto, le condizioni sono molto migliori.</p>
<p>La funzione <strong>"Tratti da valutare"</strong> individua i tratti nei quali si combinano due informazioni:</p>
<p><strong>LTS elevato + importanza del tratto nella connessione della rete.</strong></p>
<p>Non significa <strong>"qui bisogna costruire una pista ciclabile"</strong>.</p>
<p>Significa piuttosto: <strong>"questo tratto merita attenzione"</strong>.</p>
<p>Intervenire in un punto strategico può infatti migliorare la continuità di una parte molto più grande della rete.</p>
<h3>Il ruolo di OpenStreetMap</h3>
<p><a href="https://www.openstreetmap.org" target="_blank" rel="noopener"><strong>OpenStreetMap</strong></a> non è soltanto una mappa di sfondo: i suoi dati sono alla base del calcolo dell'LTS.</p>
<p>Accessibilità alle biciclette, tipo di strada, infrastrutture ciclabili, limiti di velocità e numero di corsie sono alcune delle informazioni ricavate da OSM.</p>
<p>Per capire come OpenStreetMap descrive l'accessibilità in bicicletta puoi consultare la <a href="https://wiki.openstreetmap.org/wiki/IT:Key:bicycle" target="_blank" rel="noopener"><strong>pagina wiki dedicata alla tassonomia bicycle</strong></a>.</p>
<p>OpenStreetMap è collaborativa: se un'informazione è mancante o sbagliata può essere corretta dalla comunità.</p>
<p><strong>Stress in bici non si aggiorna però in tempo reale.</strong> La mappa viene ricalcolata periodicamente, quindi le modifiche fatte su OpenStreetMap potranno essere recepite negli aggiornamenti successivi.</p>
<p>I dati derivati da OpenStreetMap sono distribuiti con licenza <a href="https://opendatacommons.org/licenses/odbl/summary/" target="_blank" rel="noopener"><strong>ODbL</strong></a>, con attribuzione a <strong>© OpenStreetMap contributors</strong>.</p>
<h3>Da dove nasce il progetto</h3>
<p><strong>Stress in bici</strong> non nasce da zero.</p>
<p>Alla base ci sono gli studi sulle <strong>reti ciclabili a basso stress</strong>, tra cui i lavori di <a href="https://peterfurth.sites.northeastern.edu/" target="_blank" rel="noopener"><strong>Peter Furth</strong></a>, e l'esperienza di <a href="https://bikeottawa.ca/" target="_blank" rel="noopener"><strong>BikeOttawa</strong></a>, che ha sviluppato un <a href="https://maps.bikeottawa.ca/lts/" target="_blank" rel="noopener"><strong>modello aperto</strong></a> per classificare le strade utilizzando OpenStreetMap.</p>
<p>Nel 2021 <a href="https://github.com/napo" target="_blank" rel="noopener"><strong>Maurizio Napolitano</strong></a> e <a href="https://github.com/mfortini" target="_blank" rel="noopener"><strong>Matteo Fortini</strong></a> hanno sperimentato questo approccio in Italia con il progetto <a href="https://medium.com/tantotanto/lo-stress-dei-percorsi-ciclabili-ee7573ec8284" target="_blank" rel="noopener"><strong>Bici stressate dal traffico</strong></a>.</p>
<p>Il lavoro è poi proseguito con la <strong>tesi di Master in Data Science di <a href="https://leoventuroso.github.io/" target="_blank" rel="noopener">Leonardo Venturoso</a></strong>, che ha permesso di approfondire e ampliare il modello.</p>
<p>Da questa esperienza è nato <a href="https://github.com/dclfbk/LTSBikePlan" target="_blank" rel="noopener"><strong>LTS-BikePlan</strong></a>, con l'adattamento dell'LTS al contesto italiano, la pendenza, l'analisi della connettività e lo studio della relazione con gli incidenti.</p>
<h3>Un progetto aperto</h3>
<p><strong>Stress in bici è un progetto aperto.</strong></p>
<p>Il <a href="https://github.com/dclfbk/LTSBikePlan" target="_blank" rel="noopener"><strong>codice sorgente è pubblico</strong></a>, così il metodo può essere controllato, discusso, riutilizzato e migliorato.</p>
<p>La metodologia è descritta nell'articolo scientifico:</p>
<p><strong>Venturoso, L., Usmani, M., Nanni, R., &amp; Napolitano, M. (2026). <em>LTS-BikePlan: A Data-Driven Tool for Enhancing Cycling Infrastructure and Safety</em>. Journal of Urban Technology, 1&ndash;42.</strong></p>
<p><a href="https://doi.org/10.1080/10630732.2026.2639290" target="_blank" rel="noopener"><strong>DOI 10.1080/10630732.2026.2639290</strong></a></p>
<p><strong>Stress in bici</strong> prova a guardare le strade italiane dalla prospettiva delle persone che le percorrono in bicicletta: per capire quali generano meno stress, quali ne generano di più e quali punti della rete meritano maggiore attenzione.</p>
<p><strong>Hai dubbi su come vengono calcolati i valori, sul significato dell'LTS o sui limiti della mappa? Dai un'occhiata alle <a href="#" id="open-faq-link">FAQ</a>.</strong></p>`,
    // FAQ content (see aboutBody above and the "third nav link" pattern
    // setupInfoPanel already anticipates) - Italian only for now, same
    // reasoning as aboutBody: EN/DE/FR keep their own separate About
    // content until this gets translated. No faqItems fallback needed in
    // those blocks - t() already falls back to I18N.it for any key a
    // language doesn't define.
    faqItems: [
      {
        q: "Che cos'è l'LTS?",
        a: `<p><strong>LTS</strong> significa <strong>Level of Traffic Stress</strong>.</p>
<p>È un indicatore che classifica le strade in base al livello di stress che le loro caratteristiche possono generare nelle persone che le percorrono in bicicletta.</p>
<p>Tiene conto di elementi come il tipo di strada, la presenza di infrastrutture ciclabili, il limite di velocità, il numero di corsie, i parcheggi e la larghezza della carreggiata.</p>`,
      },
      {
        q: "Cosa significano LTS 1, 2, 3 e 4?",
        a: `<p>La scala va da 1 a 4:</p>
<ul>
<li><strong>LTS 1</strong> - stress molto basso</li>
<li><strong>LTS 2</strong> - stress basso</li>
<li><strong>LTS 3</strong> - stress elevato</li>
<li><strong>LTS 4</strong> - stress molto elevato</li>
</ul>
<p>Più aumenta il valore, più le caratteristiche della strada possono rendere impegnativa l'esperienza in bicicletta.</p>`,
      },
      {
        q: "Perché in alcuni casi non riesco ad attivare tutti i livelli LTS dalla legenda?",
        a: `<p>Per mantenere leggibile la mappa quando si vede una porzione ampia di territorio, i livelli LTS vengono mostrati gradualmente man mano che si aumenta lo zoom:</p>
<ul>
<li><strong>Zoom 4-7</strong> - solo <strong>LTS 1</strong> e <strong>LTS 2</strong> (stress basso)</li>
<li><strong>Zoom 8-11</strong> - si aggiunge <strong>LTS 3</strong></li>
<li><strong>Zoom 12 e oltre</strong> - tutti i livelli, incluso <strong>LTS 4</strong> e le strade non ciclabili</li>
</ul>
<p>Mostrare da subito ogni strada di ogni livello, su tutta l'Italia, avrebbe reso la mappa una macchia di colore poco leggibile. Nella legenda le voci non ancora disponibili al livello di zoom corrente compaiono <strong>disattivate</strong>, con l'indicazione dello zoom da cui si sbloccano: basta avvicinarsi alla zona di interesse per vederle.</p>
<p>Una volta sbloccata, ogni voce resta comunque cliccabile per mostrarla o nasconderla, esattamente come prima.</p>`,
      },
      {
        q: "LTS 4 significa che una strada è pericolosa?",
        a: `<p>No.</p>
<p>L'LTS <strong>non è un indice di incidentalità</strong> e non misura direttamente la probabilità di avere un incidente.</p>
<p>Una strada con LTS 4 può essere percepita come molto impegnativa a causa del traffico, della velocità o delle sue caratteristiche, ma questo non significa necessariamente che sia la strada dove avvengono più incidenti.</p>
<p>Allo stesso modo, un valore LTS basso non garantisce che una strada sia priva di rischi.</p>
<p>In altre parole, Stress in bici non prova a rispondere alla domanda <strong>"Questa strada è sicura?"</strong>, ma piuttosto a <strong>"Quanto stress può generare questa strada quando la percorro in bici?"</strong></p>`,
      },
      {
        q: "Perché considerate anche la pendenza?",
        a: `<p>Perché non c'è solo il traffico.</p>
<p>Una strada può avere buone caratteristiche infrastrutturali, ma una salita lunga e molto ripida può comunque cambiare parecchio l'esperienza di chi la percorre.</p>
<p>Nel nostro adattamento dell'LTS, quando una salita è sufficientemente lunga e ripida il valore può aumentare.</p>
<p>La pendenza viene calcolata da un modello digitale del terreno con una risoluzione di circa 10 metri. Su un tratto molto corto (pochi metri) questa misura può non essere affidabile: per questo la penalità si applica solo ai tratti di almeno 500 metri, dove il dato è stabile.</p>
<p>La vista 3D della mappa aiuta anche a leggere questo aspetto del territorio.</p>`,
      },
      {
        q: "Da dove arrivano i dati?",
        a: `<p>Principalmente da <strong>OpenStreetMap - OSM</strong>.</p>
<p>Utilizziamo le informazioni presenti nel database per descrivere le caratteristiche delle strade: accessibilità alle biciclette, tipologia stradale, infrastrutture ciclabili, limiti di velocità, corsie e altri attributi utili al calcolo.</p>
<p>Per approfondire come OpenStreetMap descrive l'accessibilità alle biciclette puoi consultare la <a href="https://wiki.openstreetmap.org/wiki/IT:Key:bicycle" target="_blank" rel="noopener">wiki OSM dedicata alla chiave <code>bicycle</code></a>.</p>`,
      },
      {
        q: "Ho trovato una strada classificata male. Cosa posso fare?",
        a: `<p>La prima cosa da controllare sono i dati presenti in OpenStreetMap.</p>
<p>Se un'informazione è mancante o sbagliata, può essere corretta direttamente su OSM.</p>
<p>Questo però <strong>non modifica immediatamente Stress in bici</strong>.</p>
<p>La nostra mappa viene ricalcolata periodicamente. Una correzione fatta oggi su OpenStreetMap potrà quindi essere recepita in uno degli aggiornamenti successivi.</p>`,
      },
      {
        q: "Quanto sono affidabili i risultati?",
        a: `<p>Dipende anche dalla qualità dei dati disponibili.</p>
<p>L'algoritmo applica le stesse regole in modo automatico a una grande quantità di strade, ma OpenStreetMap può avere dati mancanti, incompleti o non aggiornati.</p>
<p>Per questo <strong>Stress in bici è uno strumento di lettura e analisi, non una verità assoluta sulla strada</strong>.</p>
<p>Se un risultato sembra strano, vale la pena capire quali dati lo hanno prodotto.</p>`,
      },
      {
        q: "Perché alcune informazioni mancanti vengono stimate?",
        a: `<p>Non tutte le strade in OpenStreetMap hanno ogni attributo necessario al calcolo.</p>
<p>Nel modello LTS-BikePlan alcuni valori mancanti vengono quindi stimati sulla base della tipologia della strada e delle regole adottate per il contesto italiano.</p>
<p>Questo permette di calcolare l'LTS anche dove i dati non sono completi, ma è un altro motivo per cui migliorare OpenStreetMap è importante.</p>`,
      },
      {
        q: 'Cosa sono i "Tratti da valutare"?',
        a: `<p>Non sono semplicemente tutte le strade con LTS alto.</p>
<p>Le strade formano una rete e alcuni tratti hanno un ruolo più importante di altri nel collegarla.</p>
<p>La funzione <strong>"Tratti da valutare"</strong> mette in evidenza i punti nei quali si combinano:</p>
<p><strong>LTS elevato + importanza del tratto nella connessione della rete.</strong></p>
<p>Un breve tratto ad alto stress può, per esempio, interrompere il collegamento tra due zone dove le condizioni sono molto migliori.</p>`,
      },
      {
        q: 'Un "tratto da valutare" significa che lì bisogna costruire una pista ciclabile?',
        a: `<p>No.</p>
<p>L'algoritmo non decide quale intervento realizzare.</p>
<p>Segnala un tratto che <strong>merita attenzione</strong> per il suo livello di stress e per il ruolo che svolge nella rete.</p>
<p>Capire se sia necessario intervenire e come farlo richiede poi una valutazione sul posto, dati aggiuntivi e competenze di pianificazione e progettazione.</p>`,
      },
      {
        q: 'Perché una strada con LTS 4 potrebbe non comparire tra i "Tratti da valutare"?',
        a: `<p>Perché avere un LTS elevato è solo una parte del problema.</p>
<p>Una strada con LTS 4 può avere un ruolo marginale nella rete, mentre un tratto con LTS 3 può essere un passaggio fondamentale per collegare due grandi aree a basso stress.</p>
<p>Per questo vengono considerate insieme <strong>caratteristiche della strada e struttura della rete</strong>.</p>`,
      },
      {
        q: "Gli incidenti vengono usati per calcolare l'LTS?",
        a: `<p>No.</p>
<p>LTS e incidentalità misurano aspetti diversi.</p>
<p>LTS-BikePlan ha però sperimentato l'integrazione con dati storici di <strong>incidenti georeferenziati</strong>, mettendo in relazione incidenti, LTS e struttura della rete.</p>
<p>Se in futuro fossero disponibili banche dati omogenee e sufficientemente complete, questo tipo di informazione potrebbe arricchire ulteriormente Stress in bici.</p>`,
      },
      {
        q: "Perché non usate semplicemente il numero di incidenti?",
        a: `<p>Perché il numero di incidenti racconta solo una parte della storia.</p>
<p>Un tratto può avere pochi incidenti anche perché pochissime persone scelgono di percorrerlo in bicicletta.</p>
<p>Al contrario, una strada molto frequentata può avere più incidenti pur presentando condizioni percepite come migliori.</p>
<p>Per confrontare correttamente questi aspetti servono dati sufficientemente completi sull'incidentalità e, idealmente, anche sui flussi ciclistici.</p>`,
      },
      {
        q: "Stress in bici serve come navigatore?",
        a: `<p>Non è questo il suo obiettivo principale.</p>
<p>La mappa nasce soprattutto per <strong>osservare e analizzare le caratteristiche della rete stradale dal punto di vista di chi si muove in bicicletta</strong> e per individuare possibili punti critici.</p>
<p>Il valore LTS può naturalmente essere utile anche per ragionare sui percorsi, ma Stress in bici non vuole sostituire un sistema di navigazione.</p>`,
      },
      {
        q: "Posso usare i dati?",
        a: `<p>Sì.</p>
<p>I dati derivano principalmente da OpenStreetMap e sono distribuiti secondo le condizioni della licenza <strong>ODbL</strong>, mantenendo l'attribuzione a <strong>© OpenStreetMap contributors</strong>.</p>
<p>Anche il codice del progetto è pubblico e può essere studiato, verificato e migliorato.</p>`,
      },
      {
        q: "Dove trovo il codice?",
        a: `<p>Il codice di <strong>LTS-BikePlan</strong> è disponibile su GitHub:</p>
<p><a href="https://github.com/dclfbk/LTSBikePlan" target="_blank" rel="noopener">github.com/dclfbk/LTSBikePlan</a></p>`,
      },
      {
        q: "Esiste una pubblicazione scientifica?",
        a: `<p>Sì.</p>
<p>La metodologia è descritta in:</p>
<p><strong>Venturoso, L., Usmani, M., Nanni, R., &amp; Napolitano, M. (2026). <em>LTS-BikePlan: A Data-Driven Tool for Enhancing Cycling Infrastructure and Safety</em>. Journal of Urban Technology, 1&ndash;42.</strong></p>
<p><a href="https://doi.org/10.1080/10630732.2026.2639290" target="_blank" rel="noopener">DOI 10.1080/10630732.2026.2639290</a></p>`,
      },
      {
        q: "Da dove nasce Stress in bici?",
        a: `<p>Il progetto parte dagli studi sulle reti ciclabili a basso stress e dall'esperienza di <strong>BikeOttawa</strong>.</p>
<p>Nel 2021 <strong>Maurizio Napolitano e Matteo Fortini</strong> hanno sperimentato questo approccio in Italia con <a href="https://medium.com/tantotanto/lo-stress-dei-percorsi-ciclabili-ee7573ec8284" target="_blank" rel="noopener"><strong>Bici stressate dal traffico</strong></a>.</p>
<p>Il lavoro è poi proseguito con la tesi di Master in Data Science di <strong>Leonardo Venturoso</strong> e con lo sviluppo di <strong>LTS-BikePlan</strong>, da cui deriva l'approccio utilizzato in Stress in bici.</p>`,
      },
      {
        q: "Come funziona il calcolo del percorso e del tempo stimato?",
        a: `<p>Il calcolo del percorso è <strong>sperimentale</strong> e viene eseguito interamente sul tuo dispositivo, non su un server: il tracciato preferisce le strade con LTS più basso, ma <strong>non tiene conto del traffico in tempo reale</strong>, perché non è un dato disponibile.</p>
<p>I tratti classificati come <strong>non ciclabili</strong> (LTS 0) non vengono presi in considerazione: se l'unico collegamento verso una destinazione passa da lì, il percorso potrebbe non essere calcolabile.</p>
<p>Il tempo stimato viene calcolato sia per una <strong>bicicletta muscolare</strong> (velocità di base 18 km/h in piano) sia per una <strong>bicicletta elettrica</strong> (velocità di base 22 km/h in piano, rallentata molto meno in salita grazie all'assistenza del motore), entrambe ridotte in salita e aumentate (fino a un limite) in discesa, in base alla pendenza reale rilevata dal modello del terreno lungo il percorso.</p>
<p>Non considera vento, forma fisica, semafori o soste: va preso come un'indicazione di massima, non come un tempo di percorrenza garantito.</p>`,
      },
      {
        q: "Posso segnalare un problema o proporre un miglioramento?",
        a: `<p>Sì, ed è proprio uno degli obiettivi di un progetto aperto.</p>
<p>Per una strada classificata male vale quanto detto sopra: si corregge su OpenStreetMap, non qui.</p>
<p>Per tutto il resto - <strong>l'algoritmo, il calcolo o il software</strong> - il codice pubblico permette di verificare il funzionamento e contribuire al suo miglioramento.</p>`,
      },
    ],
    privacyToggle: "Cookie",
    privacyHeading: "Privacy e cookie",
    privacyIntro: "Questo sito non usa cookie di tracciamento, né servizi di analisi o pubblicità: non viene raccolto alcun dato di navigazione. Se in futuro venissero introdotti strumenti che li richiedono, questa pagina sarà aggiornata con le informazioni necessarie e le opzioni per gestire il consenso.",
    comuniNavLink: "Confronta comuni",
    mapNavLink: "Mappa",
    comuniTitle: "Confronta i comuni",
    comuniSubtitle: "Indicatori LTS calcolati per ogni comune già elaborato, con dati anagrafici ISTAT.",
    comuniPopulationNote: "Popolazione e densità abitativa non ancora disponibili.",
    comuniFilterRegione: "Regione",
    comuniFilterProvincia: "Provincia",
    comuniFilterSearch: "Cerca comune...",
    comuniFilterCapoluoghi: "Solo capoluoghi",
    comuniAllRegioni: "Tutte le regioni",
    comuniAllProvince: "Tutte le province",
    comuniColComune: "Comune",
    comuniColRegione: "Regione",
    comuniColProvincia: "Provincia",
    comuniColSuperficie: "Superficie (km²)",
    comuniColTotalKm: "Rete totale (km)",
    comuniColLowStressKm: "Km a basso stress",
    comuniColLowStressShare: "% basso stress",
    comuniColSeparatedKm: "Km percorsi separati",
    comuniColPriorityKm: "Km da valutare",
    comuniColIslands: "Isole a basso stress",
    comuniEmpty: "Nessun comune trovato con questi filtri.",
    comuniCapoluogoProvincia: "capoluogo di provincia",
    comuniCapoluogoRegione: "capoluogo di regione",
    footerCredit: `Un progetto di <a href="https://github.com/napo" target="_blank" rel="noopener">Maurizio Napolitano</a> e <a href="https://leoventuroso.github.io/" target="_blank" rel="noopener">Leonardo Venturoso</a>`,
    footerHosting: "Si ringrazia TOP-IX per l'hosting",
    gapHeading: "Tratti da valutare",
    gapHint: "Elenco dei tratti ad alto stress che interrompono la rete a basso stress, ordinati dal più critico e da quanto quella via è importante per attraversare la zona. Clicca una via per evidenziarla ed andarci. Si aggiorna in base a quello che vedi sulla mappa.",
    gapEmpty: "Nessun tratto da valutare nella vista corrente - sposta o allontana la mappa.",
    gapZoomHint: "Aumenta lo zoom per vedere i tratti da valutare in quest'area.",
    gapUrgency: { "4": "Intervento prioritario", "3": "Da valutare" },
    centralityTemplate: (phrase) => `È ${phrase}.`,
    centrality: {
      zero: "un collegamento locale, poco attraversato dai percorsi più brevi",
      low: "un collegamento secondario nella rete",
      medium: "una via di collegamento nella zona",
      high: "una strada importante per i collegamenti della zona",
      very_high: "un passaggio quasi obbligato per attraversare quest'area",
    },
    popupNoName: "Strada senza nome",
    popupComune: "Comune",
    popupDetails: "Dettagli avanzati",
    popupMaxspeed: "Velocità max",
    popupLanes: "Corsie",
    popupSlope: "Pendenza",
    popupLength: "Lunghezza",
    popupRule: "Motivazione LTS",
    popupOsmLink: "Apri su OpenStreetMap ↗",
    surfaceTemplate: (phrase) => `Strada ${phrase}.`,
    cyclewayTemplate: (phrase) => `Strada con ${phrase}.`,
    surfacePenaltyTemplate: (delta) => `Fondo sconnesso: LTS aumentato di ${delta}.`,
    lts: {
      "1": "LTS 1 - molto tranquillo", "2": "LTS 2 - tranquillo", "3": "LTS 3 - impegnativo",
      "4": "LTS 4 - molto impegnativo", "0": "Non ciclabile", fallback: "Dato insufficiente",
    },
    surface: {
      asphalt: "asfaltata", paved: "pavimentata", concrete: "in cemento",
      "concrete:plates": "in lastre di cemento", "concrete:lanes": "in cemento a corsie",
      paving_stones: "pavimentata a lastre", sett: "pavimentata a sampietrini",
      cobblestone: "pavimentata a ciottoli", unhewn_cobblestone: "pavimentata a ciottoli grezzi",
      metal: "con fondo metallico", wood: "con fondo in legno",
      gravel: "in ghiaia", fine_gravel: "in ghiaino", pebblestone: "in ciottoli sciolti",
      dirt: "sterrata", earth: "sterrata", ground: "in terreno naturale",
      mud: "fangosa", sand: "sabbiosa", grass: "erbosa", grass_paver: "erbosa su grigliato",
      unpaved: "non pavimentata", compacted: "in terra compattata", snow: "innevata", ice: "ghiacciata",
    },
    cycleway: {
      lane: "corsia ciclabile", track: "pista ciclabile separata",
      shared_lane: "pista ciclabile condivisa", share_busway: "corsia condivisa con gli autobus",
      opposite: "corsia ciclabile in controsenso", opposite_lane: "corsia ciclabile in controsenso",
      opposite_track: "pista ciclabile separata in controsenso",
      separate: "pista ciclabile su percorso separato", shoulder: "banchina ciclabile",
      crossing: "attraversamento ciclabile",
    },
    slope: {
      "0-3: flat": "pianeggiante", "3-5: mild": "leggera", "5-8: medium": "media",
      "8-10: hard": "impegnativa", "10-20: extreme": "molto impegnativa", ">20: impossible": "estrema",
    },
    rules: {
      p2: "Ciclabilità non consentita: la bicicletta è espressamente vietata su questo tratto.",
      p6: "Ciclabilità non consentita: l'accesso a questo tratto è vietato.",
      p3: "Ciclabilità non consentita: è un'autostrada.",
      p4: "Ciclabilità non consentita: è una rampa di accesso autostradale.",
      p7: "Ciclabilità non consentita: è una strada ancora in progetto, non esistente sul terreno.",
      p5: "Ciclabilità non consentita: è un marciapiede su cui non è espressamente indicato l'uso in bicicletta.",
      p8: "Ciclabilità non consentita: è una scalinata priva di rampa per biciclette.",
      p9: "LTS impostato a 1: è una scalinata dotata di rampa per biciclette.",
      p10: "Ciclabilità non consentita: è una strada a scorrimento veloce (motorroad) di categoria trunk, vietata alle biciclette per legge.",
      p11: "Ciclabilità non consentita: l'accesso è riservato (privato, con permesso, clienti, destinazione, uso agricolo/forestale/militare) e non è indicato un permesso esplicito per le biciclette.",
      p12: "Ciclabilità non consentita: è un passo carraio, una corsia interna a un parcheggio o un accesso riservato ai mezzi di soccorso, e non è indicato un permesso esplicito per le biciclette.",
      s3: "Questo tratto è una pista ciclabile separata dal traffico.",
      s1: "Questo tratto è un sentiero o percorso separato dalla circolazione motorizzata.",
      s2: "Questo tratto è un percorso pedonale separato dal traffico, non un attraversamento.",
      s7: "Questo tratto è un percorso separato perché ha una pista ciclabile fisicamente distinta dalla carreggiata.",
      s8: "Questo tratto è un percorso separato perché ha una pista ciclabile distinta dalla carreggiata, percorribile in controsenso.",
      s9: "Ciclabilità non consentita: è un sentiero di montagna troppo impegnativo per una bicicletta da città o elettrica.",
      b1: "LTS è 1: corsia ciclabile con parcheggio, velocità massima fino a 40 km/h, strada a basso potenziale di scorrimento di autoveicoli con al massimo 2 corsie.",
      b2: "LTS portato a 3 perché ci sono 3 o più corsie ed è presente parcheggio.",
      b3: "LTS portato a 3 perché la larghezza della corsia ciclabile è inferiore a 4,1m ed è presente parcheggio.",
      b4: "LTS portato a 2 perché la larghezza della corsia ciclabile è inferiore a 4,25m ed è presente parcheggio.",
      b5: "LTS portato a 2 perché la larghezza della corsia ciclabile è inferiore a 4,5m, la velocità massima è inferiore a 40 su una strada a basso potenziale di scorrimento di autoveicoli ed è presente parcheggio.",
      b6: "LTS portato a 2 perché la velocità massima è tra 41-50 km/h ed è presente parcheggio.",
      b7: "LTS portato a 3 perché la velocità massima è tra 51-54 km/h ed è presente parcheggio.",
      b8: "LTS portato a 4 perché la velocità massima supera i 55 km/h ed è presente parcheggio.",
      b9: "LTS portato a 3: la strada con corsia ciclabile e parcheggio ha un alto potenziale di scorrimento di autoveicoli.",
      c1: "LTS è 1: corsia ciclabile senza parcheggio, velocità massima fino a 50 km/h, strada a basso potenziale di scorrimento di autoveicoli con al massimo 2 corsie.",
      c3: "LTS portato a 3 perché ci sono 3 o più corsie e non c'è parcheggio.",
      c4: "LTS portato a 2 perché la larghezza della corsia ciclabile è inferiore a 1,7 metri e non c'è parcheggio.",
      c5: "LTS portato a 3 perché la velocità massima è tra 51-64 km/h e non c'è parcheggio.",
      c6: "LTS portato a 4 perché la velocità massima supera i 65 km/h e non c'è parcheggio.",
      c7: "LTS portato a 3: la strada con corsia ciclabile senza parcheggio ha un alto potenziale di scorrimento di autoveicoli.",
      m17: "LTS impostato a 1: i veicoli a motore non sono ammessi su questo tratto.",
      m13: "LTS impostato a 1: è una zona pedonale.",
      m14: "LTS impostato a 2: è un attraversamento pedonale.",
      m2: "LTS impostato a 2: è un vicolo di servizio.",
      m15: "LTS impostato a 2: è una strada sterrata o agricola.",
      m3: "LTS impostato a 2: velocità massima fino a 50 km/h, corsia interna a un parcheggio.",
      m4: "LTS impostato a 2: velocità massima fino a 50 km/h, passo carraio o vialetto privato.",
      m16: "LTS impostato a 2: velocità massima inferiore a 35 km/h, strada di servizio.",
      m5: "LTS impostato a 2: velocità massima fino a 40 km/h, al massimo 3 corsie, strada a basso potenziale di scorrimento di autoveicoli.",
      m6: "LTS impostato a 3 perché la velocità massima è fino a 40 km/h e 3 corsie o meno su una strada ad alto potenziale di scorrimento di autoveicoli.",
      m7: "LTS impostato a 3 perché la velocità massima è fino a 40 km/h e ci sono 4 o 5 corsie.",
      m8: "LTS impostato a 4 perché la velocità massima è fino a 40 km/h e il numero di corsie supera 5.",
      m9: "LTS impostato a 2: velocità massima fino a 50 km/h, al massimo 2 corsie, strada a basso potenziale di scorrimento di autoveicoli.",
      m10: "LTS impostato a 3 perché la velocità massima è fino a 50 km/h e le corsie sono 3 o meno su una strada ad alto potenziale di scorrimento di autoveicoli.",
      m11: "LTS impostato a 4 perché il numero di corsie supera 3.",
      m12: "LTS impostato a 4 perché la velocità massima supera i 50 km/h.",
    },
  },

  en: {
    legendToggle: "Legend",
    legendHint: "Click to show/hide",
    legendZoomDisabledHint: "Visible from zoom {zoom} onward",
    bgLight: "Light background",
    bgSummer: "Summer background",
    bgCycling: "Cycling background",
    bgDark: "Dark background",
    terrainToggle: "3D terrain",
    printControl: "Print map",
    shareButton: "Share",
    shareCopied: "Copied!",
    shareModalHeading: "Share this view",
    shareUrlLabel: "Link",
    shareCopyButton: "Copy",
    shareEmbedLabel: "Embed code (iframe)",
    shareSocialLabel: "Share on social media",
    shareIntentText: "Visit Stress in Bici to explore the cycling stress of Italian roads",
    shareMastodonInstancePrompt: "Your Mastodon server (e.g. mastodon.social)",
    pdfCenterLabel: "Center",
    pdfScaleLabel: "Scale",
    geocoderPlaceholder: "Search a place...",
    routingToggle: "Route",
    routingStartLabel: "Start",
    routingEndLabel: "End",
    routingClickHint: "Click on the map<br>to set start and end",
    routingDisclaimerSummary: "How this calculation works",
    routingDisclaimerBody: "The route favours the lowest-stress (LTS) stretches available and excludes segments classified as not suitable for cycling: if the only connection to a destination runs through one, a route may not be found. It doesn't account for real-time traffic, since that data isn't available. This is an experimental engine that computes the route locally, on your own device. The estimated time is calculated for both a regular and an electric bike, and accounts for the terrain's real gradient, but not wind, fitness level, or stops.",
    routingBikeMuscularLabel: "Regular bike",
    routingBikeElectricLabel: "E-bike",
    routeEstimatedTimeTemplate: (h, m) => (h > 0 ? `~${h} h ${m} min` : `~${m} min`),
    routingClearButton: "Clear",
    routingCalculating: "Calculating route...",
    routingNoRoute: "No route found: start and end don't appear to be connected yet by mapped low-stress roads.",
    routingPartialRouteTemplate: (km) => `Partial route: past this point (marked in orange) the road isn't cyclable. The destination is still about ${km} km away.`,
    routingNoCoverage: "Routing isn't available in this area yet.",
    routeKmSoFar: "Distance so far",
    routeTotalKm: "Total length",
    routeElevationHeading: "Elevation profile",
    routeLtsSegmentTemplate: (km, pct, descriptor) => `${km}km (${pct}%) of ${descriptor} riding`,
    routeFacilitySegmentTemplate: (km, pct, label) => `${km}km (${pct}%) of ${label}`,
    routeDownloadHeading: "Download route",
    routeDownloadGeoJson: "GeoJSON",
    routeDownloadGpx: "GPX",
    routeDownloadKml: "KML",
    loadingTitle: "Loading...",
    zoomHint: "Zoom in to see the roads",
    zoomClickHint: "Zoom in further to click a road",
    facilityStreet: "Street",
    facilityCycleway: "Cycleway",
    facilityPath: "Path / unpaved trail",
    gapToggle: "Segments to evaluate",
    aboutToggle: "About",
    faqToggle: "FAQ",
    faqHeading: "FAQ",
    faqCloseAndScrollUp: "Close and scroll to top",
    aiTranslationNote: "Translation by AI",
    aboutHeading: "Stress in bici",
    aboutSubtitle: "How much stress can a street generate when you ride it by bike?",
    aboutBody: `<p><strong>Stress in bici</strong> is a map that tries to answer a simple question: <strong>how much stress can a street generate when you ride it by bike?</strong></p>
<p>To do this it uses <strong>LTS &ndash; Level of Traffic Stress</strong>, a method that describes how comfortable or demanding a road can be for cyclists.</p>
<p>LTS doesn't directly measure collision risk: it tries instead to represent the sense of comfort, discomfort, or perceived danger in relation to traffic and the road's characteristics.</p>
<p>Every segment is classified from <strong>LTS 1</strong>, the calmest, to <strong>LTS 4</strong>, the most demanding.</p>
<p>The calculation takes into account elements such as road type, cycling infrastructure, speed, number of lanes, parking, and carriageway width.</p>
<h3>Where it comes from</h3>
<p>The idea builds on research into <strong>low-stress bicycle networks</strong>, in particular the work of Peter Furth and collaborators, and on the experience of <strong>Bike Ottawa</strong>, which developed an open model for computing LTS using OpenStreetMap data.</p>
<p>In 2021 <strong>Maurizio Napolitano and Matteo Fortini</strong> tried out this approach in Italy with the project <a href="https://medium.com/tantotanto/lo-stress-dei-percorsi-ciclabili-ee7573ec8284" target="_blank" rel="noopener"><strong>Bici stressate dal traffico</strong></a> ("Bikes stressed by traffic").</p>
<p>Later, thanks to <strong>Leonardo Venturoso's Master's thesis in Data Science</strong>, the algorithm was refined, adapted to the Italian context, and enriched with new analyses. This work is the origin of <strong>LTS-BikePlan</strong>, described in the scientific paper this map is based on.</p>
<h3>Hills matter too</h3>
<p>Traffic isn't the only thing that can make a ride feel less calm.</p>
<p>A road can be protected and lightly trafficked, yet a long, steep climb can still make it much more demanding.</p>
<p>That's why the model used here also considers <strong>slope</strong>: when a climb is long and steep enough, the LTS value can increase.</p>
<h3>Where would it be most useful to act?</h3>
<p>Not all roads carry the same weight in the network.</p>
<p>A segment with high LTS can be particularly significant when it's an important link between areas that are otherwise calm to ride through.</p>
<p>That's why the map also offers the <strong>"Segments to evaluate"</strong> function.</p>
<p>It highlights segments where <strong>high LTS</strong> and <strong>an important role in the road network's connectivity</strong> combine. The analysis comes directly from the methods used to identify high-stress links that break up low-stress networks.</p>
<p>It doesn't necessarily mean <strong>"a bike lane must be built here."</strong></p>
<p>It means, rather:</p>
<p><strong>"This is worth a closer look."</strong></p>
<p>Improving one of these points could make a much larger part of the network more continuous and usable.</p>
<h3>A map built with OpenStreetMap</h3>
<p>Road characteristics come primarily from <strong>OpenStreetMap</strong>.</p>
<p>The classification uses information such as bicycle accessibility, road type, cycle paths and lanes, speed, and number of lanes.</p>
<p>The reference documentation describing bicycle accessibility is available on the <a href="https://wiki.openstreetmap.org/wiki/Key:bicycle" target="_blank" rel="noopener">OpenStreetMap wiki</a>.</p>
<p>And there's an interesting consequence: <strong>if a piece of data in OpenStreetMap is wrong or incomplete, it can be fixed</strong>.</p>
<p>The map is updated periodically, so an improvement in OSM data can be reflected in later calculations. The quality and completeness of OpenStreetMap are in fact one of the factors that influence the result.</p>
<p>Data derived from OpenStreetMap is distributed under the <strong>ODbL</strong> licence, with attribution to <strong>&copy; OpenStreetMap contributors</strong>.</p>
<h3>What about collisions?</h3>
<p>A road that's calm to ride isn't automatically a road without collisions.</p>
<p><strong>LTS and collision rates are two different things.</strong></p>
<p>The LTS-BikePlan work specifically studies the relationship between these two phenomena, and shows how LTS can be combined with a <strong>georeferenced collision history</strong> to produce even more useful analyses when assessing critical points.</p>
<p>This is also one of the map's possible future directions: combining road characteristics, network connectivity, and historical collision data.</p>
<h3>Open, verifiable, improvable</h3>
<p>The project is <strong>open source</strong>.</p>
<p>The rules and code used to compute the indicators are public, so the method can be verified, discussed, and improved.</p>
<p>The methodology is described in the scientific article:</p>
<p><strong>Venturoso, L., Usmani, M., Nanni, R., &amp; Napolitano, M. (2026). <em>LTS-BikePlan: A Data-Driven Tool for Enhancing Cycling Infrastructure and Safety</em>. Journal of Urban Technology, 1&ndash;42.</strong></p>
<p><a href="https://doi.org/10.1080/10630732.2026.2639290" target="_blank" rel="noopener">DOI 10.1080/10630732.2026.2639290</a></p>
<p>The goal isn't to pass a final judgment on every road.</p>
<p>It's to offer <strong>a different way of looking at the Italian road network from a cyclist's point of view</strong>.</p>
<p>To understand where it's calm to ride.</p>
<p>And, above all, <strong>where riding could be better</strong>.</p>`,
    privacyToggle: "Cookie",
    privacyHeading: "Privacy & cookies",
    privacyIntro: "This site does not use tracking cookies, analytics, or advertising services: no browsing data is collected. If tools that require them are introduced in the future, this page will be updated with the necessary information and consent options.",
    comuniNavLink: "Compare municipalities",
    mapNavLink: "Map",
    comuniTitle: "Compare municipalities",
    comuniSubtitle: "LTS indicators computed for every processed municipality, with ISTAT administrative data.",
    comuniPopulationNote: "Population and population density aren't available yet.",
    comuniFilterRegione: "Region",
    comuniFilterProvincia: "Province",
    comuniFilterSearch: "Search municipality...",
    comuniFilterCapoluoghi: "Capitals only",
    comuniAllRegioni: "All regions",
    comuniAllProvince: "All provinces",
    comuniColComune: "Municipality",
    comuniColRegione: "Region",
    comuniColProvincia: "Province",
    comuniColSuperficie: "Surface (km²)",
    comuniColTotalKm: "Total network (km)",
    comuniColLowStressKm: "Low-stress km",
    comuniColLowStressShare: "% low-stress",
    comuniColSeparatedKm: "Separated-path km",
    comuniColPriorityKm: "Km to evaluate",
    comuniColIslands: "Low-stress islands",
    comuniEmpty: "No municipality matches these filters.",
    comuniCapoluogoProvincia: "provincial capital",
    comuniCapoluogoRegione: "regional capital",
    footerCredit: `A project by <a href="https://github.com/napo" target="_blank" rel="noopener">Maurizio Napolitano</a> and <a href="https://leoventuroso.github.io/" target="_blank" rel="noopener">Leonardo Venturoso</a>`,
    footerHosting: "Thanks to TOP-IX for hosting",
    gapHeading: "Segments to evaluate",
    gapHint: "High-stress segments that break up the low-stress network, ranked by severity and by how important that street is for crossing the area. Click a street to highlight it and fly there. Updates based on what's currently visible on the map.",
    gapEmpty: "No segments to evaluate in the current view - pan or zoom out the map.",
    gapZoomHint: "Zoom in to see segments to evaluate in this area.",
    gapUrgency: { "4": "Priority intervention", "3": "To evaluate" },
    centralityTemplate: (phrase) => `It's ${phrase}.`,
    centrality: {
      zero: "a local connector, rarely used by the shortest routes",
      low: "a minor link in the network",
      medium: "a connecting street in the area",
      high: "an important street for the area's connectivity",
      very_high: "an almost mandatory passage to cross this area",
    },
    popupNoName: "Unnamed road",
    popupComune: "Municipality",
    popupDetails: "Advanced details",
    popupMaxspeed: "Max speed",
    popupLanes: "Lanes",
    popupSlope: "Slope",
    popupLength: "Length",
    popupRule: "LTS rationale",
    popupOsmLink: "Open on OpenStreetMap ↗",
    surfaceTemplate: (phrase) => `${phrase} road.`,
    cyclewayTemplate: (phrase) => `Road with ${phrase}.`,
    lts: {
      "1": "LTS 1 - very comfortable", "2": "LTS 2 - comfortable", "3": "LTS 3 - demanding",
      "4": "LTS 4 - very demanding", "0": "Not bikeable", fallback: "Insufficient data",
    },
    surface: {
      asphalt: "Asphalt", paved: "Paved", concrete: "Concrete",
      "concrete:plates": "Concrete slab", "concrete:lanes": "Concrete lane",
      paving_stones: "Paving stone", sett: "Cobblestone (sett)",
      cobblestone: "Cobblestone", unhewn_cobblestone: "Rough cobblestone",
      metal: "Metal-surfaced", wood: "Wooden",
      gravel: "Gravel", fine_gravel: "Fine gravel", pebblestone: "Pebblestone",
      dirt: "Dirt", earth: "Dirt", ground: "Natural-ground",
      mud: "Muddy", sand: "Sandy", grass: "Grass", grass_paver: "Grass-paver",
      unpaved: "Unpaved", compacted: "Compacted-earth", snow: "Snow-covered", ice: "Icy",
    },
    cycleway: {
      lane: "a bike lane", track: "a separated bike path",
      shared_lane: "a shared bike lane", share_busway: "a lane shared with buses",
      opposite: "a contraflow bike lane", opposite_lane: "a contraflow bike lane",
      opposite_track: "a separated contraflow bike path",
      separate: "a bike path on a separate way", shoulder: "a cyclable shoulder",
      crossing: "a bike crossing",
    },
    slope: {
      "0-3: flat": "flat", "3-5: mild": "mild", "5-8: medium": "moderate",
      "8-10: hard": "steep", "10-20: extreme": "very steep", ">20: impossible": "extreme",
    },
    rules: {
      p2: "Cycling not permitted: bicycles are explicitly banned on this segment.",
      p6: "Cycling not permitted: access to this segment is restricted.",
      p3: "Cycling not permitted: it's a motorway.",
      p4: "Cycling not permitted: it's a motorway slip road.",
      p7: "Cycling not permitted: it's a planned road that doesn't exist on the ground yet.",
      p5: "Cycling not permitted: it's a sidewalk with no explicit indication that cycling is allowed.",
      p8: "Cycling not permitted: it's a flight of stairs with no bicycle ramp.",
      p9: "LTS set to 1: it's a flight of stairs with a bicycle ramp.",
      p10: "Cycling not permitted: it's a trunk-class expressway (motorroad), off-limits to bicycles by law.",
      p11: "Cycling not permitted: access is restricted (private, permit, customers, destination, agricultural/forestry/military use) with no explicit permission for bicycles.",
      p12: "Cycling not permitted: it's a driveway, a parking-lot lane, or an emergency-vehicle-only access road, with no explicit permission for bicycles.",
      s3: "This way is a cycle path physically separated from traffic.",
      s1: "This way is a path separated from motor traffic.",
      s2: "This way is a footpath separated from traffic, not a crossing.",
      s7: "This way is separated because it has a cycle track physically distinct from the roadway.",
      s8: "This way is separated because it has a cycle track distinct from the roadway, usable in the opposite direction.",
      s9: "Cycling not permitted: it's a mountain trail too demanding for a city or e-bike.",
      b1: "LTS is 1: bike lane with parking, maxspeed up to 40 km/h, low motor-vehicle-flow street with 2 lanes or fewer.",
      b2: "Increasing LTS to 3 because there are 3 or more lanes and parking present.",
      b3: "Increasing LTS to 3 because the bike lane width is less than 4.1m and parking present.",
      b4: "Increasing LTS to 2 because the bike lane width is less than 4.25m and parking present.",
      b5: "Increasing LTS to 2 because the bike lane width is less than 4.5m, maxspeed is less than 40 on a low motor-vehicle-flow street and parking present.",
      b6: "Increasing LTS to 2 because the maxspeed is between 41-50 km/h and parking present.",
      b7: "Increasing LTS to 3 because the maxspeed is between 51-54 km/h and parking present.",
      b8: "Increasing LTS to 4 because the maxspeed is over 55 km/h and parking present.",
      b9: "Increasing LTS to 3: the street with bike lane and parking is a high motor-vehicle-flow street.",
      c1: "LTS is 1: bike lane with no parking, maxspeed up to 50 km/h, low motor-vehicle-flow street with 2 lanes or fewer.",
      c3: "Increasing LTS to 3 because there are 3 or more lanes and no parking.",
      c4: "Increasing LTS to 2 because the bike lane width is less than 1.7 metres and no parking.",
      c5: "Increasing LTS to 3 because the maxspeed is between 51-64 km/h and no parking.",
      c6: "Increasing LTS to 4 because the maxspeed is over 65 km/h and no parking.",
      c7: "Increasing LTS to 3: the street with bike lane and no parking is a high motor-vehicle-flow street.",
      m17: "Setting LTS to 1: motor vehicles aren't allowed on this segment.",
      m13: "Setting LTS to 1: it's a pedestrian zone.",
      m14: "Setting LTS to 2: it's a pedestrian crossing.",
      m2: "Setting LTS to 2: it's a service alley.",
      m15: "Setting LTS to 2: it's an unpaved or agricultural track.",
      m3: "Setting LTS to 2: maxspeed up to 50 km/h, a parking lot aisle.",
      m4: "Setting LTS to 2: maxspeed up to 50 km/h, a private driveway.",
      m16: "Setting LTS to 2: maxspeed under 35 km/h, a service road.",
      m5: "Setting LTS to 2: maxspeed up to 40 km/h, 3 lanes or fewer, low motor-vehicle-flow street.",
      m6: "Setting LTS to 3 because maxspeed is up to 40 km/h and 3 or fewer lanes on a high motor-vehicle-flow street.",
      m7: "Setting LTS to 3 because maxspeed is up to 40 km/h and 4 or 5 lanes.",
      m8: "Setting LTS to 4 because maxspeed is up to 40 km/h and the number of lanes is greater than 5.",
      m9: "Setting LTS to 2: maxspeed up to 50 km/h, 2 lanes or fewer, low motor-vehicle-flow street.",
      m10: "Setting LTS to 3 because maxspeed is up to 50 km/h and lanes are 3 or less on a high motor-vehicle-flow street.",
      m11: "Setting LTS to 4 because the number of lanes is greater than 3.",
      m12: "Setting LTS to 4 because maxspeed is greater than 50 km/h.",
    },
  },

  de: {
    legendToggle: "Legende",
    legendHint: "Klicken zum Ein-/Ausblenden",
    legendZoomDisabledHint: "Sichtbar ab Zoomstufe {zoom}",
    bgLight: "Heller Hintergrund",
    bgSummer: "Sommer-Hintergrund",
    bgCycling: "Rad-Hintergrund",
    bgDark: "Dunkler Hintergrund",
    terrainToggle: "3D-Gelände",
    printControl: "Karte drucken",
    shareButton: "Teilen",
    shareCopied: "Kopiert!",
    shareModalHeading: "Diese Ansicht teilen",
    shareUrlLabel: "Link",
    shareCopyButton: "Kopieren",
    shareEmbedLabel: "Einbettungscode (iframe)",
    shareSocialLabel: "In sozialen Netzwerken teilen",
    shareIntentText: "Besuchen Sie Stress in Bici, um den Radfahrstress auf italienischen Straßen zu entdecken",
    shareMastodonInstancePrompt: "Ihr Mastodon-Server (z. B. mastodon.social)",
    pdfCenterLabel: "Zentrum",
    pdfScaleLabel: "Maßstab",
    geocoderPlaceholder: "Ort suchen...",
    routingToggle: "Route",
    routingStartLabel: "Start",
    routingEndLabel: "Ziel",
    routingClickHint: "Klicken Sie auf die Karte,<br>um Start und Ziel festzulegen",
    routingDisclaimerSummary: "So funktioniert diese Berechnung",
    routingDisclaimerBody: "Die Route bevorzugt Abschnitte mit niedrigerem Stressniveau (LTS) und berücksichtigt keine Abschnitte, die als nicht fahrradgeeignet eingestuft sind: Führt die einzige Verbindung zu einem Ziel dort hindurch, kann möglicherweise keine Route gefunden werden. Der Echtzeitverkehr wird nicht berücksichtigt, da diese Daten nicht verfügbar sind. Es handelt sich um eine experimentelle Engine, die die Route lokal auf Ihrem eigenen Gerät berechnet. Die geschätzte Zeit wird sowohl für ein normales als auch für ein Elektrofahrrad berechnet und berücksichtigt die reale Geländesteigung, aber nicht Wind, Fitness oder Pausen.",
    routingBikeMuscularLabel: "Normales Fahrrad",
    routingBikeElectricLabel: "E-Bike",
    routeEstimatedTimeTemplate: (h, m) => (h > 0 ? `~${h} Std ${m} Min` : `~${m} Min`),
    routingClearButton: "Löschen",
    routingCalculating: "Route wird berechnet...",
    routingNoRoute: "Keine Route gefunden: Start und Ziel scheinen noch nicht durch kartierte stressarme Straßen verbunden zu sein.",
    routingPartialRouteTemplate: (km) => `Teilstrecke: Ab diesem Punkt (orange markiert) ist die Straße nicht mit dem Fahrrad befahrbar. Das Ziel ist noch etwa ${km} km entfernt.`,
    routingNoCoverage: "Routing ist in diesem Gebiet noch nicht verfügbar.",
    routeKmSoFar: "Zurückgelegte Strecke",
    routeTotalKm: "Gesamtlänge",
    routeElevationHeading: "Höhenprofil",
    routeLtsSegmentTemplate: (km, pct, descriptor) => `${km}km (${pct}%) auf einer Strecke, die ${descriptor} ist`,
    routeFacilitySegmentTemplate: (km, pct, label) => `${km}km (${pct}%) auf ${label}`,
    routeDownloadHeading: "Route herunterladen",
    routeDownloadGeoJson: "GeoJSON",
    routeDownloadGpx: "GPX",
    routeDownloadKml: "KML",
    loadingTitle: "Wird geladen...",
    zoomHint: "Zoomen Sie hinein, um die Straßen zu sehen",
    zoomClickHint: "Zoomen Sie weiter hinein, um eine Straße anzuklicken",
    facilityStreet: "Straße",
    facilityCycleway: "Radweg",
    facilityPath: "Pfad / unbefestigter Weg",
    gapToggle: "Abschnitte zur Bewertung",
    aboutToggle: "Info",
    faqToggle: "FAQ",
    faqHeading: "FAQ",
    faqCloseAndScrollUp: "Schließen und nach oben",
    aiTranslationNote: "Übersetzung durch KI",
    aboutHeading: "Stress in bici",
    aboutSubtitle: "Wie viel Stress kann eine Straße verursachen, wenn man sie mit dem Fahrrad befährt?",
    aboutBody: `<p><strong>Stress in bici</strong> ist eine Karte, die eine einfache Frage zu beantworten versucht: <strong>Wie viel Stress kann eine Straße verursachen, wenn man sie mit dem Fahrrad befährt?</strong></p>
<p>Dafür wird der <strong>LTS &ndash; Level of Traffic Stress</strong> verwendet, eine Methode, die beschreibt, wie komfortabel oder anspruchsvoll eine Straße für Radfahrende sein kann.</p>
<p>Der LTS misst nicht direkt das Unfallrisiko: Er versucht vielmehr, das Gefühl von Komfort, Unbehagen oder wahrgenommener Gefahr im Verhältnis zu Verkehr und Straßenmerkmalen darzustellen.</p>
<p>Jeder Abschnitt wird von <strong>LTS 1</strong>, dem entspanntesten, bis <strong>LTS 4</strong>, dem anspruchsvollsten, eingestuft.</p>
<p>Die Berechnung berücksichtigt Elemente wie Straßentyp, Radinfrastruktur, Geschwindigkeit, Anzahl der Fahrspuren, Parken und Fahrbahnbreite.</p>
<h3>Woher die Idee kommt</h3>
<p>Die Idee stützt sich auf Studien zu <strong>Radnetzen mit geringer Verkehrsbelastung</strong>, insbesondere die Arbeiten von Peter Furth und Kollegen, sowie auf die Erfahrung von <strong>Bike Ottawa</strong>, das ein offenes Modell zur Berechnung des LTS anhand von OpenStreetMap-Daten entwickelt hat.</p>
<p>2021 haben <strong>Maurizio Napolitano und Matteo Fortini</strong> diesen Ansatz in Italien mit dem Projekt <a href="https://medium.com/tantotanto/lo-stress-dei-percorsi-ciclabili-ee7573ec8284" target="_blank" rel="noopener"><strong>Bici stressate dal traffico</strong></a> ("Vom Verkehr gestresste Fahrräder") erprobt.</p>
<p>Später wurde der Algorithmus dank der <strong>Masterarbeit in Data Science von Leonardo Venturoso</strong> vertieft, an den italienischen Kontext angepasst und um neue Analysen erweitert. Aus dieser Arbeit ist <strong>LTS-BikePlan</strong> entstanden, beschrieben im wissenschaftlichen Paper, auf dem diese Karte basiert.</p>
<h3>Auch Steigungen zählen</h3>
<p>Der Verkehr ist nicht das Einzige, was eine Fahrt weniger entspannt machen kann.</p>
<p>Eine Straße kann geschützt und wenig befahren sein, aber ein langer, steiler Anstieg kann sie trotzdem deutlich anspruchsvoller machen.</p>
<p>Deshalb berücksichtigt das hier verwendete Modell auch die <strong>Steigung</strong>: Wenn ein Anstieg lang und steil genug ist, kann sich der LTS-Wert erhöhen.</p>
<h3>Wo würde sich ein Eingriff am meisten lohnen?</h3>
<p>Nicht alle Straßen haben das gleiche Gewicht im Netz.</p>
<p>Ein Abschnitt mit hohem LTS kann besonders interessant sein, wenn er eine wichtige Verbindung zwischen ansonsten entspannt befahrbaren Gebieten darstellt.</p>
<p>Deshalb bietet die Karte auch die Funktion <strong>"Abschnitte zur Bewertung"</strong>.</p>
<p>Hier werden Abschnitte hervorgehoben, in denen sich <strong>ein hoher LTS</strong> und <strong>eine wichtige Rolle für die Konnektivität des Straßennetzes</strong> verbinden. Die Analyse stammt direkt aus den Methoden, mit denen stark belastete Verbindungen identifiziert werden, die Netze mit geringer Verkehrsbelastung unterbrechen.</p>
<p>Das bedeutet nicht zwangsläufig <strong>"hier muss ein Radweg gebaut werden."</strong></p>
<p>Es bedeutet vielmehr:</p>
<p><strong>"Hier lohnt sich ein genauerer Blick."</strong></p>
<p>Die Verbesserung eines dieser Punkte könnte einen deutlich größeren Teil des Netzes durchgängiger und nutzbarer machen.</p>
<h3>Eine mit OpenStreetMap erstellte Karte</h3>
<p>Die Straßenmerkmale stammen hauptsächlich aus <strong>OpenStreetMap</strong>.</p>
<p>Die Klassifizierung nutzt Informationen wie Fahrradzugänglichkeit, Straßentyp, Radwege und -spuren, Geschwindigkeit und Anzahl der Fahrspuren.</p>
<p>Die Referenzdokumentation zur Beschreibung der Fahrradzugänglichkeit ist im <a href="https://wiki.openstreetmap.org/wiki/DE:Key:bicycle" target="_blank" rel="noopener">OpenStreetMap-Wiki</a> verfügbar.</p>
<p>Und daraus ergibt sich eine interessante Konsequenz: <strong>Wenn ein Datum in OpenStreetMap falsch oder unvollständig ist, kann es korrigiert werden</strong>.</p>
<p>Die Karte wird regelmäßig aktualisiert, sodass sich eine Verbesserung der OSM-Daten in späteren Berechnungen niederschlagen kann. Die Qualität und Vollständigkeit von OpenStreetMap sind tatsächlich einer der Faktoren, die das Ergebnis beeinflussen.</p>
<p>Die von OpenStreetMap abgeleiteten Daten werden unter der Lizenz <strong>ODbL</strong> mit Namensnennung <strong>&copy; OpenStreetMap contributors</strong> weitergegeben.</p>
<h3>Und die Unfälle?</h3>
<p>Eine entspannt befahrbare Straße ist nicht automatisch eine Straße ohne Unfälle.</p>
<p><strong>LTS und Unfallhäufigkeit sind zwei verschiedene Dinge.</strong></p>
<p>Die Arbeit LTS-BikePlan untersucht genau die Beziehung zwischen diesen Phänomenen und zeigt, wie sich der LTS mit einer <strong>georeferenzierten Unfallhistorie</strong> kombinieren lässt, um noch nützlichere Analysen bei der Bewertung kritischer Stellen zu erhalten.</p>
<p>Dies ist auch eine der möglichen Weiterentwicklungen der Karte: Straßenmerkmale, Netzkonnektivität und historische Unfalldaten zu kombinieren.</p>
<h3>Offen, überprüfbar, verbesserbar</h3>
<p>Das Projekt ist <strong>Open Source</strong>.</p>
<p>Die Regeln und der Code zur Berechnung der Indikatoren sind öffentlich, sodass die Methode überprüft, diskutiert und verbessert werden kann.</p>
<p>Die Methodik wird im wissenschaftlichen Artikel beschrieben:</p>
<p><strong>Venturoso, L., Usmani, M., Nanni, R., &amp; Napolitano, M. (2026). <em>LTS-BikePlan: A Data-Driven Tool for Enhancing Cycling Infrastructure and Safety</em>. Journal of Urban Technology, 1&ndash;42.</strong></p>
<p><a href="https://doi.org/10.1080/10630732.2026.2639290" target="_blank" rel="noopener">DOI 10.1080/10630732.2026.2639290</a></p>
<p>Das Ziel ist es nicht, ein endgültiges Urteil über jede Straße zu fällen.</p>
<p>Es geht darum, <strong>eine andere Sichtweise auf das italienische Straßennetz aus der Perspektive von Radfahrenden</strong> anzubieten.</p>
<p>Um zu verstehen, wo man entspannt Rad fahren kann.</p>
<p>Und vor allem, <strong>wo man besser Rad fahren könnte</strong>.</p>`,
    privacyToggle: "Cookies",
    privacyHeading: "Datenschutz und Cookies",
    privacyIntro: "Diese Website verwendet keine Tracking-Cookies, keine Analyse- und keine Werbedienste: Es werden keine Nutzungsdaten erfasst. Sollten künftig Werkzeuge eingeführt werden, die dies erfordern, wird diese Seite mit den nötigen Informationen und Einwilligungsoptionen aktualisiert.",
    comuniNavLink: "Gemeinden vergleichen",
    mapNavLink: "Karte",
    comuniTitle: "Gemeinden vergleichen",
    comuniSubtitle: "LTS-Indikatoren für jede verarbeitete Gemeinde, mit ISTAT-Verwaltungsdaten.",
    comuniPopulationNote: "Bevölkerung und Bevölkerungsdichte sind noch nicht verfügbar.",
    comuniFilterRegione: "Region",
    comuniFilterProvincia: "Provinz",
    comuniFilterSearch: "Gemeinde suchen...",
    comuniFilterCapoluoghi: "Nur Hauptstädte",
    comuniAllRegioni: "Alle Regionen",
    comuniAllProvince: "Alle Provinzen",
    comuniColComune: "Gemeinde",
    comuniColRegione: "Region",
    comuniColProvincia: "Provinz",
    comuniColSuperficie: "Fläche (km²)",
    comuniColTotalKm: "Netz gesamt (km)",
    comuniColLowStressKm: "Km mit geringer Belastung",
    comuniColLowStressShare: "% geringe Belastung",
    comuniColSeparatedKm: "Km getrennte Wege",
    comuniColPriorityKm: "Zu bewertende km",
    comuniColIslands: "Inseln geringer Belastung",
    comuniEmpty: "Keine Gemeinde entspricht diesen Filtern.",
    comuniCapoluogoProvincia: "Provinzhauptstadt",
    comuniCapoluogoRegione: "Regionalhauptstadt",
    footerCredit: `Ein Projekt von <a href="https://github.com/napo" target="_blank" rel="noopener">Maurizio Napolitano</a> und <a href="https://leoventuroso.github.io/" target="_blank" rel="noopener">Leonardo Venturoso</a>`,
    footerHosting: "Dank an TOP-IX für das Hosting",
    gapHeading: "Abschnitte zur Bewertung",
    gapHint: "Stark belastete Abschnitte, die das Netz mit geringer Verkehrsbelastung unterbrechen, sortiert nach Dringlichkeit und danach, wie wichtig die Straße für die Durchquerung des Gebiets ist. Klicke auf eine Straße, um sie hervorzuheben und dorthin zu springen. Wird an den aktuell sichtbaren Kartenausschnitt angepasst.",
    gapEmpty: "Keine Abschnitte zur Bewertung im aktuellen Kartenausschnitt - Karte verschieben oder verkleinern.",
    gapZoomHint: "Zoome näher heran, um Abschnitte zur Bewertung in diesem Gebiet zu sehen.",
    gapUrgency: { "4": "Vorrangige Maßnahme", "3": "Zu prüfen" },
    centralityTemplate: (phrase) => `Das ist ${phrase}.`,
    centrality: {
      zero: "eine lokale Verbindung, die kaum auf kürzesten Wegen liegt",
      low: "eine untergeordnete Verbindung im Netz",
      medium: "eine Verbindungsstraße im Gebiet",
      high: "eine wichtige Straße für die Erschließung des Gebiets",
      very_high: "nahezu ein Pflichtdurchgang, um dieses Gebiet zu durchqueren",
    },
    popupNoName: "Straße ohne Namen",
    popupComune: "Gemeinde",
    popupDetails: "Erweiterte Details",
    popupMaxspeed: "Höchstgeschwindigkeit",
    popupLanes: "Fahrspuren",
    popupSlope: "Steigung",
    popupLength: "Länge",
    popupRule: "LTS-Begründung",
    popupOsmLink: "Auf OpenStreetMap öffnen ↗",
    surfaceTemplate: (phrase) => `Straße mit ${phrase}.`,
    cyclewayTemplate: (phrase) => `Straße mit ${phrase}.`,
    lts: {
      "1": "LTS 1 - sehr entspannt", "2": "LTS 2 - entspannt", "3": "LTS 3 - anspruchsvoll",
      "4": "LTS 4 - sehr anspruchsvoll", "0": "Nicht befahrbar", fallback: "Unzureichende Daten",
    },
    surface: {
      asphalt: "Asphaltbelag", paved: "befestigtem Belag", concrete: "Betonbelag",
      "concrete:plates": "Betonplatten", "concrete:lanes": "Beton-Fahrspuren",
      paving_stones: "Pflastersteinen", sett: "Kopfsteinpflaster",
      cobblestone: "Kopfsteinpflaster", unhewn_cobblestone: "grobem Kopfsteinpflaster",
      metal: "Metallbelag", wood: "Holzbelag",
      gravel: "Kiesbelag", fine_gravel: "Feinkies", pebblestone: "losem Schotter",
      dirt: "unbefestigtem Untergrund", earth: "unbefestigtem Untergrund", ground: "natürlichem Untergrund",
      mud: "schlammigem Untergrund", sand: "sandigem Untergrund", grass: "Gras", grass_paver: "Rasengittersteinen",
      unpaved: "unbefestigtem Belag", compacted: "verdichtetem Erdboden", snow: "Schnee", ice: "Eis",
    },
    cycleway: {
      lane: "Radfahrstreifen", track: "getrenntem Radweg",
      shared_lane: "gemeinsam genutztem Radfahrstreifen", share_busway: "einer mit Bussen geteilten Spur",
      opposite: "Radfahrstreifen im Gegenverkehr", opposite_lane: "Radfahrstreifen im Gegenverkehr",
      opposite_track: "getrenntem Radweg im Gegenverkehr",
      separate: "separat geführtem Radweg", shoulder: "befahrbarem Seitenstreifen",
      crossing: "einer Radquerung",
    },
    slope: {
      "0-3: flat": "eben", "3-5: mild": "leicht", "5-8: medium": "mittel",
      "8-10: hard": "anspruchsvoll", "10-20: extreme": "sehr anspruchsvoll", ">20: impossible": "extrem",
    },
    rules: {
      p2: "Radfahren nicht erlaubt: Fahrräder sind auf diesem Abschnitt ausdrücklich verboten.",
      p6: "Radfahren nicht erlaubt: Der Zugang zu diesem Abschnitt ist gesperrt.",
      p3: "Radfahren nicht erlaubt: Es handelt sich um eine Autobahn.",
      p4: "Radfahren nicht erlaubt: Es handelt sich um eine Autobahnauffahrt.",
      p7: "Radfahren nicht erlaubt: Es handelt sich um eine geplante, noch nicht existierende Straße.",
      p5: "Radfahren nicht erlaubt: Es handelt sich um einen Gehweg ohne ausdrückliche Freigabe für Radfahrer.",
      p8: "Radfahren nicht erlaubt: Es handelt sich um eine Treppe ohne Fahrradrampe.",
      p9: "LTS auf 1 gesetzt: Es handelt sich um eine Treppe mit Fahrradrampe.",
      p10: "Radfahren nicht erlaubt: Es handelt sich um eine Schnellstraße (motorroad) der Kategorie trunk, gesetzlich für Fahrräder gesperrt.",
      p11: "Radfahren nicht erlaubt: Der Zugang ist eingeschränkt (privat, mit Erlaubnis, Kunden, Ziel, land-/forstwirtschaftliche/militärische Nutzung) und es liegt keine ausdrückliche Freigabe für Fahrräder vor.",
      p12: "Radfahren nicht erlaubt: Es handelt sich um eine private Zufahrt, eine Parkplatzfahrgasse oder eine nur für Rettungsfahrzeuge zugängliche Straße, ohne ausdrückliche Freigabe für Fahrräder.",
      s3: "Getrennter Weg: baulich vom Verkehr getrennter Radweg.",
      s1: "Getrennter Weg: vom motorisierten Verkehr getrennter Weg.",
      s2: "Getrennter Weg: vom Verkehr getrennter Gehweg, keine Querung.",
      s7: "Getrennter Weg: baulich von der Fahrbahn getrennter Radweg.",
      s8: "Getrennter Weg: von der Fahrbahn getrennter Radweg, in Gegenrichtung befahrbar.",
      s9: "Radfahren nicht erlaubt: Es handelt sich um einen Bergpfad, der für ein Stadt- oder E-Bike zu anspruchsvoll ist.",
      b1: "LTS ist 1: Radstreifen mit Parken, Höchstgeschwindigkeit bis 40 km/h, Straße mit geringem Kfz-Verkehrsaufkommen mit höchstens 2 Fahrspuren.",
      b2: "LTS auf 3 erhöht, da 3 oder mehr Fahrspuren und Parken vorhanden sind.",
      b3: "LTS auf 3 erhöht, da die Radstreifenbreite unter 4,1 m liegt und Parken vorhanden ist.",
      b4: "LTS auf 2 erhöht, da die Radstreifenbreite unter 4,25 m liegt und Parken vorhanden ist.",
      b5: "LTS auf 2 erhöht, da die Radstreifenbreite unter 4,5 m liegt, die Höchstgeschwindigkeit auf einer Straße mit geringem Kfz-Verkehrsaufkommen unter 40 km/h liegt und Parken vorhanden ist.",
      b6: "LTS auf 2 erhöht, da die Höchstgeschwindigkeit zwischen 41-50 km/h liegt und Parken vorhanden ist.",
      b7: "LTS auf 3 erhöht, da die Höchstgeschwindigkeit zwischen 51-54 km/h liegt und Parken vorhanden ist.",
      b8: "LTS auf 4 erhöht, da die Höchstgeschwindigkeit über 55 km/h liegt und Parken vorhanden ist.",
      b9: "LTS auf 3 erhöht: Die Straße mit Radstreifen und Parken hat ein hohes Kfz-Verkehrsaufkommen.",
      c1: "LTS ist 1: Radstreifen ohne Parken, Höchstgeschwindigkeit bis 50 km/h, Straße mit geringem Kfz-Verkehrsaufkommen mit höchstens 2 Fahrspuren.",
      c3: "LTS auf 3 erhöht, da 3 oder mehr Fahrspuren und kein Parken vorhanden sind.",
      c4: "LTS auf 2 erhöht, da die Radstreifenbreite unter 1,7 m liegt und kein Parken vorhanden ist.",
      c5: "LTS auf 3 erhöht, da die Höchstgeschwindigkeit zwischen 51-64 km/h liegt und kein Parken vorhanden ist.",
      c6: "LTS auf 4 erhöht, da die Höchstgeschwindigkeit über 65 km/h liegt und kein Parken vorhanden ist.",
      c7: "LTS auf 3 erhöht: Die Straße mit Radstreifen ohne Parken hat ein hohes Kfz-Verkehrsaufkommen.",
      m17: "LTS auf 1 gesetzt: Kraftfahrzeuge sind auf diesem Abschnitt nicht zugelassen.",
      m13: "LTS auf 1 gesetzt: Es handelt sich um eine Fußgängerzone.",
      m14: "LTS auf 2 gesetzt: Es handelt sich um einen Fußgängerüberweg.",
      m2: "LTS auf 2 gesetzt: Es handelt sich um eine Hintergasse.",
      m15: "LTS auf 2 gesetzt: Es handelt sich um einen unbefestigten Wirtschaftsweg.",
      m3: "LTS auf 2 gesetzt: Höchstgeschwindigkeit bis 50 km/h, Fahrgasse eines Parkplatzes.",
      m4: "LTS auf 2 gesetzt: Höchstgeschwindigkeit bis 50 km/h, private Zufahrt.",
      m16: "LTS auf 2 gesetzt: Höchstgeschwindigkeit unter 35 km/h, Erschließungsstraße.",
      m5: "LTS auf 2 gesetzt: Höchstgeschwindigkeit bis 40 km/h, höchstens 3 Fahrspuren, Straße mit geringem Kfz-Verkehrsaufkommen.",
      m6: "LTS auf 3 gesetzt, da die Höchstgeschwindigkeit bis 40 km/h beträgt und höchstens 3 Fahrspuren auf einer Straße mit hohem Kfz-Verkehrsaufkommen vorhanden sind.",
      m7: "LTS auf 3 gesetzt, da die Höchstgeschwindigkeit bis 40 km/h beträgt und 4 oder 5 Fahrspuren vorhanden sind.",
      m8: "LTS auf 4 gesetzt, da die Höchstgeschwindigkeit bis 40 km/h beträgt und mehr als 5 Fahrspuren vorhanden sind.",
      m9: "LTS auf 2 gesetzt: Höchstgeschwindigkeit bis 50 km/h, höchstens 2 Fahrspuren, Straße mit geringem Kfz-Verkehrsaufkommen.",
      m10: "LTS auf 3 gesetzt, da die Höchstgeschwindigkeit bis 50 km/h beträgt und höchstens 3 Fahrspuren auf einer Straße mit hohem Kfz-Verkehrsaufkommen vorhanden sind.",
      m11: "LTS auf 4 gesetzt, da mehr als 3 Fahrspuren vorhanden sind.",
      m12: "LTS auf 4 gesetzt, da die Höchstgeschwindigkeit über 50 km/h liegt.",
    },
  },

  fr: {
    legendToggle: "Légende",
    legendHint: "Cliquer pour afficher/masquer",
    legendZoomDisabledHint: "Visible à partir du zoom {zoom}",
    bgLight: "Fond clair",
    bgSummer: "Fond estival",
    bgCycling: "Fond cyclable",
    bgDark: "Fond sombre",
    terrainToggle: "Relief 3D",
    printControl: "Imprimer la carte",
    shareButton: "Partager",
    shareCopied: "Copié !",
    shareModalHeading: "Partager cette vue",
    shareUrlLabel: "Lien",
    shareCopyButton: "Copier",
    shareEmbedLabel: "Code à intégrer (iframe)",
    shareSocialLabel: "Partager sur les réseaux sociaux",
    shareIntentText: "Visitez Stress in Bici pour découvrir le stress cycliste des routes italiennes",
    shareMastodonInstancePrompt: "Votre serveur Mastodon (ex. mastodon.social)",
    pdfCenterLabel: "Centre",
    pdfScaleLabel: "Échelle",
    geocoderPlaceholder: "Rechercher un lieu...",
    routingToggle: "Itinéraire",
    routingStartLabel: "Départ",
    routingEndLabel: "Arrivée",
    routingClickHint: "Cliquez sur la carte<br>pour définir le départ et l'arrivée",
    routingDisclaimerSummary: "Comment fonctionne ce calcul",
    routingDisclaimerBody: "L'itinéraire privilégie les tronçons avec le niveau de stress (LTS) le plus bas et exclut les tronçons classés comme non adaptés au vélo : si la seule liaison vers une destination passe par là, il se peut qu'aucun itinéraire ne soit trouvé. Il ne tient pas compte du trafic en temps réel, cette donnée n'étant pas disponible. Il s'agit d'un moteur expérimental qui calcule l'itinéraire localement, sur votre propre appareil. Le temps estimé est calculé à la fois pour un vélo musculaire et pour un vélo électrique, et tient compte de la pente réelle du terrain, mais pas du vent, de la forme physique ni des arrêts.",
    routingBikeMuscularLabel: "Vélo musculaire",
    routingBikeElectricLabel: "Vélo électrique",
    routeEstimatedTimeTemplate: (h, m) => (h > 0 ? `~${h} h ${m} min` : `~${m} min`),
    routingClearButton: "Effacer",
    routingCalculating: "Calcul de l'itinéraire...",
    routingNoRoute: "Aucun itinéraire trouvé : le départ et l'arrivée ne semblent pas encore reliés par des routes à faible stress cartographiées.",
    routingPartialRouteTemplate: (km) => `Itinéraire partiel : au-delà de ce point (marqué en orange), la route n'est pas cyclable. La destination est encore à environ ${km} km.`,
    routingNoCoverage: "L'itinéraire n'est pas encore disponible dans cette zone.",
    routeKmSoFar: "Distance parcourue",
    routeTotalKm: "Longueur totale",
    routeElevationHeading: "Profil altimétrique",
    routeLtsSegmentTemplate: (km, pct, descriptor) => `${km}km (${pct}%) de parcours ${descriptor}`,
    routeFacilitySegmentTemplate: (km, pct, label) => `${km}km (${pct}%) de ${label}`,
    routeDownloadHeading: "Télécharger l'itinéraire",
    routeDownloadGeoJson: "GeoJSON",
    routeDownloadGpx: "GPX",
    routeDownloadKml: "KML",
    loadingTitle: "Chargement...",
    zoomHint: "Zoomez pour voir les routes",
    zoomClickHint: "Zoomez encore pour cliquer sur une route",
    facilityStreet: "Route",
    facilityCycleway: "Piste cyclable",
    facilityPath: "Sentier / chemin non goudronné",
    gapToggle: "Tronçons à évaluer",
    aboutToggle: "À propos",
    faqToggle: "FAQ",
    faqHeading: "FAQ",
    faqCloseAndScrollUp: "Fermer et remonter",
    aiTranslationNote: "Traduction par IA",
    aboutHeading: "Stress in bici",
    aboutSubtitle: "Quel niveau de stress une route peut-elle générer quand on la parcourt à vélo ?",
    aboutBody: `<p><strong>Stress in bici</strong> est une carte qui tente de r&eacute;pondre &agrave; une question simple&nbsp;: <strong>quel niveau de stress une route peut-elle g&eacute;n&eacute;rer quand on la parcourt &agrave; v&eacute;lo&nbsp;?</strong></p>
<p>Pour cela, elle utilise le <strong>LTS &ndash; Level of Traffic Stress</strong>, une m&eacute;thode qui d&eacute;crit &agrave; quel point une route peut &ecirc;tre confortable ou exigeante pour les cyclistes.</p>
<p>Le LTS ne mesure pas directement le risque d'accident&nbsp;: il cherche plut&ocirc;t &agrave; repr&eacute;senter la sensation de confort, de g&ecirc;ne ou de danger per&ccedil;u en fonction du trafic et des caract&eacute;ristiques de la route.</p>
<p>Chaque tron&ccedil;on est class&eacute; de <strong>LTS 1</strong>, le plus tranquille, &agrave; <strong>LTS 4</strong>, le plus exigeant.</p>
<p>Le calcul tient compte d'&eacute;l&eacute;ments comme le type de route, les infrastructures cyclables, la vitesse, le nombre de voies, le stationnement et la largeur de la chauss&eacute;e.</p>
<h3>D'o&ugrave; vient l'id&eacute;e</h3>
<p>L'id&eacute;e s'appuie sur les &eacute;tudes consacr&eacute;es aux <strong>r&eacute;seaux cyclables &agrave; faible stress</strong>, en particulier les travaux de Peter Furth et de ses collaborateurs, ainsi que sur l'exp&eacute;rience de <strong>Bike Ottawa</strong>, qui a d&eacute;velopp&eacute; un mod&egrave;le ouvert pour calculer le LTS &agrave; partir des donn&eacute;es OpenStreetMap.</p>
<p>En 2021, <strong>Maurizio Napolitano et Matteo Fortini</strong> ont exp&eacute;riment&eacute; cette approche en Italie avec le projet <a href="https://medium.com/tantotanto/lo-stress-dei-percorsi-ciclabili-ee7573ec8284" target="_blank" rel="noopener"><strong>Bici stressate dal traffico</strong></a> (&laquo;&nbsp;V&eacute;los stress&eacute;s par le trafic&nbsp;&raquo;).</p>
<p>Par la suite, gr&acirc;ce au <strong>m&eacute;moire de Master en Data Science de Leonardo Venturoso</strong>, l'algorithme a &eacute;t&eacute; approfondi, adapt&eacute; au contexte italien et enrichi de nouvelles analyses. C'est de ce travail qu'est n&eacute; <strong>LTS-BikePlan</strong>, d&eacute;crit dans l'article scientifique &agrave; la base de cette carte.</p>
<h3>Les c&ocirc;tes comptent aussi</h3>
<p>Le trafic n'est pas la seule chose qui peut rendre un trajet &agrave; v&eacute;lo moins tranquille.</p>
<p>Une route peut &ecirc;tre prot&eacute;g&eacute;e et peu fr&eacute;quent&eacute;e, mais une mont&eacute;e longue et raide peut malgr&eacute; tout la rendre bien plus exigeante.</p>
<p>C'est pourquoi le mod&egrave;le utilis&eacute; ici tient aussi compte de la <strong>pente</strong>&nbsp;: lorsqu'une mont&eacute;e est suffisamment longue et raide, la valeur du LTS peut augmenter.</p>
<h3>O&ugrave; serait-il le plus utile d'intervenir&nbsp;?</h3>
<p>Toutes les routes n'ont pas la m&ecirc;me importance dans le r&eacute;seau.</p>
<p>Un tron&ccedil;on avec un LTS &eacute;lev&eacute; peut &ecirc;tre particuli&egrave;rement int&eacute;ressant lorsqu'il repr&eacute;sente une liaison importante entre des zones par ailleurs tranquilles &agrave; parcourir.</p>
<p>C'est pourquoi la carte propose aussi la fonction <strong>&laquo;&nbsp;Tron&ccedil;ons &agrave; &eacute;valuer&nbsp;&raquo;</strong>.</p>
<p>Elle met en &eacute;vidence les tron&ccedil;ons o&ugrave; se combinent <strong>un LTS &eacute;lev&eacute;</strong> et <strong>un r&ocirc;le important dans la connectivit&eacute; du r&eacute;seau routier</strong>. L'analyse d&eacute;coule pr&eacute;cis&eacute;ment des m&eacute;thodes utilis&eacute;es pour identifier les liaisons &agrave; fort stress qui interrompent les r&eacute;seaux &agrave; faible stress.</p>
<p>Cela ne signifie pas n&eacute;cessairement <strong>&laquo;&nbsp;il faut construire une piste cyclable ici&nbsp;&raquo;</strong>.</p>
<p>Cela signifie plut&ocirc;t&nbsp;:</p>
<p><strong>&laquo;&nbsp;Ici, cela vaut la peine de regarder de plus pr&egrave;s.&nbsp;&raquo;</strong></p>
<p>Am&eacute;liorer l'un de ces points pourrait en effet rendre une partie bien plus vaste du r&eacute;seau plus continue et plus utilisable.</p>
<h3>Une carte construite avec OpenStreetMap</h3>
<p>Les caract&eacute;ristiques des routes proviennent principalement d'<strong>OpenStreetMap</strong>.</p>
<p>La classification utilise des informations telles que l'accessibilit&eacute; aux v&eacute;los, le type de route, les pistes et bandes cyclables, la vitesse et le nombre de voies.</p>
<p>La documentation de r&eacute;f&eacute;rence d&eacute;crivant l'accessibilit&eacute; aux v&eacute;los est disponible sur le <a href="https://wiki.openstreetmap.org/wiki/FR:Key:bicycle" target="_blank" rel="noopener">wiki d'OpenStreetMap</a>.</p>
<p>Et cela a une cons&eacute;quence int&eacute;ressante&nbsp;: <strong>si une donn&eacute;e d'OpenStreetMap est erron&eacute;e ou incompl&egrave;te, elle peut &ecirc;tre corrig&eacute;e</strong>.</p>
<p>La carte est mise &agrave; jour p&eacute;riodiquement, si bien qu'une am&eacute;lioration des donn&eacute;es OSM peut se r&eacute;percuter sur les calculs suivants. La qualit&eacute; et l'exhaustivit&eacute; d'OpenStreetMap sont d'ailleurs l'un des &eacute;l&eacute;ments qui influencent le r&eacute;sultat.</p>
<p>Les donn&eacute;es d&eacute;riv&eacute;es d'OpenStreetMap sont distribu&eacute;es sous licence <strong>ODbL</strong>, avec attribution &agrave; <strong>&copy; OpenStreetMap contributors</strong>.</p>
<h3>Et les accidents&nbsp;?</h3>
<p>Une route tranquille &agrave; parcourir n'est pas automatiquement une route sans accidents.</p>
<p><strong>Le LTS et l'accidentalit&eacute; sont deux choses diff&eacute;rentes.</strong></p>
<p>Le travail LTS-BikePlan &eacute;tudie pr&eacute;cis&eacute;ment la relation entre ces ph&eacute;nom&egrave;nes et montre comment il est possible d'int&eacute;grer le LTS &agrave; un <strong>historique d'accidents g&eacute;or&eacute;f&eacute;renc&eacute;s</strong>, afin d'obtenir des analyses encore plus utiles pour &eacute;valuer les points critiques.</p>
<p>C'est aussi l'une des &eacute;volutions possibles de la carte&nbsp;: combiner les caract&eacute;ristiques de la route, la connectivit&eacute; du r&eacute;seau et les donn&eacute;es historiques sur les accidents.</p>
<h3>Ouvert, v&eacute;rifiable, perfectible</h3>
<p>Le projet est <strong>open source</strong>.</p>
<p>Les r&egrave;gles et le code utilis&eacute;s pour calculer les indicateurs sont publics, de sorte que la m&eacute;thode peut &ecirc;tre v&eacute;rifi&eacute;e, discut&eacute;e et am&eacute;lior&eacute;e.</p>
<p>La m&eacute;thodologie est d&eacute;crite dans l'article scientifique&nbsp;:</p>
<p><strong>Venturoso, L., Usmani, M., Nanni, R., &amp; Napolitano, M. (2026). <em>LTS-BikePlan: A Data-Driven Tool for Enhancing Cycling Infrastructure and Safety</em>. Journal of Urban Technology, 1&ndash;42.</strong></p>
<p><a href="https://doi.org/10.1080/10630732.2026.2639290" target="_blank" rel="noopener">DOI 10.1080/10630732.2026.2639290</a></p>
<p>L'objectif n'est pas de porter un jugement d&eacute;finitif sur chaque route.</p>
<p>Il s'agit d'offrir <strong>une autre mani&egrave;re de regarder le r&eacute;seau routier italien du point de vue de celles et ceux qui p&eacute;dalent</strong>.</p>
<p>Pour comprendre o&ugrave; l'on peut rouler tranquillement.</p>
<p>Et, surtout, <strong>o&ugrave; l'on pourrait mieux rouler</strong>.</p>`,
    privacyToggle: "Cookies",
    privacyHeading: "Confidentialité et cookies",
    privacyIntro: "Ce site n'utilise aucun cookie de suivi, ni service d'analyse ou de publicité : aucune donnée de navigation n'est collectée. Si des outils nécessitant ces éléments étaient introduits à l'avenir, cette page serait mise à jour avec les informations nécessaires et des options de gestion du consentement.",
    comuniNavLink: "Comparer les communes",
    mapNavLink: "Carte",
    comuniTitle: "Comparer les communes",
    comuniSubtitle: "Indicateurs LTS calculés pour chaque commune déjà traitée, avec les données administratives ISTAT.",
    comuniPopulationNote: "Population et densité de population pas encore disponibles.",
    comuniFilterRegione: "Région",
    comuniFilterProvincia: "Province",
    comuniFilterSearch: "Rechercher une commune...",
    comuniFilterCapoluoghi: "Chefs-lieux seulement",
    comuniAllRegioni: "Toutes les régions",
    comuniAllProvince: "Toutes les provinces",
    comuniColComune: "Commune",
    comuniColRegione: "Région",
    comuniColProvincia: "Province",
    comuniColSuperficie: "Superficie (km²)",
    comuniColTotalKm: "Réseau total (km)",
    comuniColLowStressKm: "Km à faible stress",
    comuniColLowStressShare: "% faible stress",
    comuniColSeparatedKm: "Km voies séparées",
    comuniColPriorityKm: "Km à évaluer",
    comuniColIslands: "Îlots à faible stress",
    comuniEmpty: "Aucune commune ne correspond à ces filtres.",
    comuniCapoluogoProvincia: "chef-lieu de province",
    comuniCapoluogoRegione: "chef-lieu de région",
    footerCredit: `Un projet de <a href="https://github.com/napo" target="_blank" rel="noopener">Maurizio Napolitano</a> et <a href="https://leoventuroso.github.io/" target="_blank" rel="noopener">Leonardo Venturoso</a>`,
    footerHosting: "Merci à TOP-IX pour l'hébergement",
    gapHeading: "Tronçons à évaluer",
    gapHint: "Tronçons à fort stress qui interrompent le réseau à faible stress, classés par gravité et par l'importance de la rue pour traverser la zone. Cliquez sur une rue pour la mettre en évidence et vous y rendre. La liste se met à jour selon la zone actuellement visible.",
    gapEmpty: "Aucun tronçon à évaluer dans la vue actuelle - déplacez ou dézoomez la carte.",
    gapZoomHint: "Zoomez pour voir les tronçons à évaluer dans cette zone.",
    gapUrgency: { "4": "Intervention prioritaire", "3": "À évaluer" },
    centralityTemplate: (phrase) => `C'est ${phrase}.`,
    centrality: {
      zero: "une liaison locale, rarement empruntée par les itinéraires les plus courts",
      low: "une liaison secondaire du réseau",
      medium: "une rue de liaison dans la zone",
      high: "une rue importante pour les liaisons de la zone",
      very_high: "un passage presque obligé pour traverser cette zone",
    },
    popupNoName: "Route sans nom",
    popupComune: "Commune",
    popupDetails: "Détails avancés",
    popupMaxspeed: "Vitesse max",
    popupLanes: "Voies",
    popupSlope: "Pente",
    popupLength: "Longueur",
    popupRule: "Justification LTS",
    popupOsmLink: "Ouvrir sur OpenStreetMap ↗",
    surfaceTemplate: (phrase) => `Route avec ${phrase}.`,
    cyclewayTemplate: (phrase) => `Route avec ${phrase}.`,
    lts: {
      "1": "LTS 1 - très tranquille", "2": "LTS 2 - tranquille", "3": "LTS 3 - exigeant",
      "4": "LTS 4 - très exigeant", "0": "Non cyclable", fallback: "Données insuffisantes",
    },
    surface: {
      asphalt: "un revêtement en asphalte", paved: "un revêtement pavé", concrete: "un revêtement en béton",
      "concrete:plates": "des dalles de béton", "concrete:lanes": "des voies en béton",
      paving_stones: "des pavés", sett: "des pavés autobloquants",
      cobblestone: "des pavés ronds", unhewn_cobblestone: "des pavés bruts",
      metal: "un revêtement métallique", wood: "un revêtement en bois",
      gravel: "du gravier", fine_gravel: "du gravillon", pebblestone: "des galets",
      dirt: "un revêtement en terre", earth: "un revêtement en terre", ground: "un sol naturel",
      mud: "un revêtement boueux", sand: "un revêtement sablonneux", grass: "de l'herbe", grass_paver: "des dalles gazon",
      unpaved: "un revêtement non pavé", compacted: "une terre compactée", snow: "de la neige", ice: "du verglas",
    },
    cycleway: {
      lane: "une bande cyclable", track: "une piste cyclable séparée",
      shared_lane: "une bande cyclable partagée", share_busway: "une voie partagée avec les bus",
      opposite: "une bande cyclable à contresens", opposite_lane: "une bande cyclable à contresens",
      opposite_track: "une piste cyclable séparée à contresens",
      separate: "une piste cyclable sur tracé séparé", shoulder: "un accotement cyclable",
      crossing: "une traversée cyclable",
    },
    slope: {
      "0-3: flat": "plat", "3-5: mild": "léger", "5-8: medium": "moyen",
      "8-10: hard": "difficile", "10-20: extreme": "très difficile", ">20: impossible": "extrême",
    },
    rules: {
      p2: "Vélo non autorisé : le vélo est explicitement interdit sur ce tronçon.",
      p6: "Vélo non autorisé : l'accès à ce tronçon est interdit.",
      p3: "Vélo non autorisé : il s'agit d'une autoroute.",
      p4: "Vélo non autorisé : il s'agit d'une bretelle d'autoroute.",
      p7: "Vélo non autorisé : il s'agit d'une route prévue, qui n'existe pas encore sur le terrain.",
      p5: "Vélo non autorisé : il s'agit d'un trottoir sans autorisation explicite pour les vélos.",
      p8: "Vélo non autorisé : il s'agit d'un escalier sans rampe pour vélos.",
      p9: "LTS fixé à 1 : il s'agit d'un escalier équipé d'une rampe pour vélos.",
      p10: "Vélo non autorisé : il s'agit d'une voie rapide (motorroad) de catégorie trunk, interdite aux vélos par la loi.",
      p11: "Vélo non autorisé : l'accès est réservé (privé, avec permis, clients, destination, usage agricole/forestier/militaire) et aucune autorisation explicite pour les vélos n'est indiquée.",
      p12: "Vélo non autorisé : il s'agit d'une allée privée, d'une allée de stationnement ou d'un accès réservé aux véhicules d'urgence, sans autorisation explicite pour les vélos.",
      s3: "Voie séparée : piste cyclable physiquement séparée de la circulation.",
      s1: "Voie séparée : chemin séparé de la circulation motorisée.",
      s2: "Voie séparée : trottoir séparé de la circulation, ce n'est pas une traversée.",
      s7: "Voie séparée : piste cyclable physiquement distincte de la chaussée.",
      s8: "Voie séparée : piste cyclable distincte de la chaussée, utilisable à contresens.",
      s9: "Vélo non autorisé : il s'agit d'un sentier de montagne trop exigeant pour un vélo de ville ou électrique.",
      b1: "LTS est 1 : bande cyclable avec stationnement, vitesse max jusqu'à 40 km/h, rue à faible potentiel de circulation automobile avec au plus 2 voies.",
      b2: "LTS porté à 3 car il y a 3 voies ou plus et du stationnement est présent.",
      b3: "LTS porté à 3 car la largeur de la bande cyclable est inférieure à 4,1 m et du stationnement est présent.",
      b4: "LTS porté à 2 car la largeur de la bande cyclable est inférieure à 4,25 m et du stationnement est présent.",
      b5: "LTS porté à 2 car la largeur de la bande cyclable est inférieure à 4,5 m, la vitesse max est inférieure à 40 km/h sur une rue à faible potentiel de circulation automobile et du stationnement est présent.",
      b6: "LTS porté à 2 car la vitesse max est comprise entre 41 et 50 km/h et du stationnement est présent.",
      b7: "LTS porté à 3 car la vitesse max est comprise entre 51 et 54 km/h et du stationnement est présent.",
      b8: "LTS porté à 4 car la vitesse max dépasse 55 km/h et du stationnement est présent.",
      b9: "LTS porté à 3 : la rue avec bande cyclable et stationnement a un fort potentiel de circulation automobile.",
      c1: "LTS est 1 : bande cyclable sans stationnement, vitesse max jusqu'à 50 km/h, rue à faible potentiel de circulation automobile avec au plus 2 voies.",
      c3: "LTS porté à 3 car il y a 3 voies ou plus et pas de stationnement.",
      c4: "LTS porté à 2 car la largeur de la bande cyclable est inférieure à 1,7 m et pas de stationnement.",
      c5: "LTS porté à 3 car la vitesse max est comprise entre 51 et 64 km/h et pas de stationnement.",
      c6: "LTS porté à 4 car la vitesse max dépasse 65 km/h et pas de stationnement.",
      c7: "LTS porté à 3 : la rue avec bande cyclable et sans stationnement a un fort potentiel de circulation automobile.",
      m17: "LTS fixé à 1 : les véhicules motorisés ne sont pas autorisés sur ce tronçon.",
      m13: "LTS fixé à 1 : il s'agit d'une zone piétonne.",
      m14: "LTS fixé à 2 : il s'agit d'une traversée piétonne.",
      m2: "LTS fixé à 2 : il s'agit d'une ruelle de service.",
      m15: "LTS fixé à 2 : il s'agit d'un chemin agricole ou forestier non revêtu.",
      m3: "LTS fixé à 2 : vitesse max jusqu'à 50 km/h, allée d'un parking.",
      m4: "LTS fixé à 2 : vitesse max jusqu'à 50 km/h, allée privée.",
      m16: "LTS fixé à 2 : vitesse max inférieure à 35 km/h, voie de desserte.",
      m5: "LTS fixé à 2 : vitesse max jusqu'à 40 km/h, au plus 3 voies, rue à faible potentiel de circulation automobile.",
      m6: "LTS fixé à 3 car la vitesse max est jusqu'à 40 km/h et au plus 3 voies sur une rue à fort potentiel de circulation automobile.",
      m7: "LTS fixé à 3 car la vitesse max est jusqu'à 40 km/h et il y a 4 ou 5 voies.",
      m8: "LTS fixé à 4 car la vitesse max est jusqu'à 40 km/h et il y a plus de 5 voies.",
      m9: "LTS fixé à 2 : vitesse max jusqu'à 50 km/h, au plus 2 voies, rue à faible potentiel de circulation automobile.",
      m10: "LTS fixé à 3 car la vitesse max est jusqu'à 50 km/h et au plus 3 voies sur une rue à fort potentiel de circulation automobile.",
      m11: "LTS fixé à 4 car il y a plus de 3 voies.",
      m12: "LTS fixé à 4 car la vitesse max dépasse 50 km/h.",
    },
  },
};
