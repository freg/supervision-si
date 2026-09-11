<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Stauts defines list urgencies an activity or action can get in (lifecylce).
 */ 
require_once('_securityCheck.php');
class MeasureUnit extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_Description;
  public $id;    // redefine $id to specify its visible place 
  public $name;
  public $pluralName;
  public $sortOrder=0;
  public $idle;
  //public $_sec_void;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="35%">${name}</th>
    <th field="pluralName" width="35%" >${pluralName}</th>
    <th field="sortOrder"  formatter="numericFormatter" width="10%">${sortOrderShort}</th>  
    <th field="idle" width="10%" formatter="booleanFormatter">${idle}</th>
    ';

  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  
  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  // ============================================================================**********
  // FUNCTIONS FOR IMPORT FACTURX
  // ============================================================================**********
  private static function normalizeUnitToken(?string $s): string {
    if ($s === null) return '';
    $s = trim(mb_strtolower($s));
    $s = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $s);
    $s = preg_replace('/[^a-z0-9]/', '', $s);
    return $s;
  }
  
  private static function getMeasureUnitIndex(): array {
    static $index = null;
    static $byId  = null;
    
    if ($index !== null) {
      return [$index, $byId];
    }
    
    $index = [];
    $byId  = [];
    
    $mu = new MeasureUnit();
    $list = $mu->getSqlElementsFromCriteria([]);
    
    foreach ($list as $row) {
      $id = (int)($row->id ?? 0);
      if ($id <= 0) continue;
      
      $name = (string)($row->name ?? '');
      $plural = (string)($row->pluralName ?? '');
      
      $byId[$id] = ['name' => $name, 'pluralName' => $plural];
      
      $k1 = self::normalizeUnitToken($name);
      if ($k1 !== '' && !isset($index[$k1])) $index[$k1] = $id;
      
      $k2 = self::normalizeUnitToken($plural);
      if ($k2 !== '' && !isset($index[$k2])) $index[$k2] = $id;
    }
    
    return [$index, $byId];
  }
  
  public static function getMeasureUnitIdFromInput(?string $input, ?int $defaultId = null, array &$missing = []): ?int {
    
    [$idx, $byId] = self::getMeasureUnitIndex();
    
    $raw = trim((string)$input);
    if ($raw === '') {
      if ($defaultId !== null) return $defaultId;
      $missing[] = '(unite vide)';
      return null;
    }
    
    $token = self::normalizeUnitToken($raw);

    if ($token !== '' && isset($idx[$token])) {
      return (int)$idx[$token];
    }
    
    $concept = null;
    
    $upper = strtoupper($raw);
    if (in_array($upper, ['DAY','MON','ANN','HUR','SET','H87','C62','MTR','MTK','MTQ','KGM','LTR'], true)) {
      $concept = $upper;
    } else {
      if (preg_match('/(day|jour|tage?|dia|giorn)/', $token)) $concept = 'DAY';
      elseif (preg_match('/(month|mois|monat|mese|mes)/', $token)) $concept = 'MON';
      elseif (preg_match('/(year|annee|jahr|anno)/', $token)) $concept = 'ANN';
      elseif (preg_match('/(hour|heure|std|ora)/', $token)) $concept = 'HUR';
      elseif (preg_match('/(lot|set|pack|bundle|paquet)/', $token)) $concept = 'SET';
      elseif (preg_match('/(piece|unit|item|pc|stk|stuck|einheit)/', $token)) $concept = 'H87';
      elseif ($token !== '' && preg_match('/^(c62)$/', $token)) $concept = 'C62';
    }
    $synonymsByConcept = [
        'DAY' => ['jour','jours','day','days','tag','tage','dia','dias','giorno','giorni'],
        'MON' => ['mois','month','months','monat','monate','mese','mesi','mes','meses'],
        'ANN' => ['an','ans','annee','annees','year','years','jahr','jahre','anno','anni'],
        'HUR' => ['heure','heures','hour','hours','std','stunde','stunden','ora','ore'],
        'SET' => ['lot','lots','set','sets','pack','packs','bundle','bundles','paquet','paquets'],
        'H87' => ['piece','pieces','unite','unites','unit','units','item','items','pc','pcs','stk','stuck'],
        'C62' => ['unite','unites','unit','units','u'],
        'MTR' => ['m','metre','metres','meter','meters'],
        'MTK' => ['m2','m²','sqm','squaremeter'],
        'MTQ' => ['m3','m³','cubicmeter'],
        'KGM' => ['kg','kilo','kilogram','kilogramme'],
        'LTR' => ['l','litre','liter'],
    ];
    
    if ($concept !== null) {
      $cands = $synonymsByConcept[$concept] ?? [];
      foreach ($cands as $cand) {
        $k = self::normalizeUnitToken($cand);
        if ($k !== '' && isset($idx[$k])) {
          return (int)$idx[$k];
        }
      }
    }

    if ($defaultId !== null) return $defaultId;
    
    $missing[] = $raw;
    return null;
  }
  
}
?>