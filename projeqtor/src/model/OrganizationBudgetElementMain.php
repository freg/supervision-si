<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
 * Budget Element is an object included in all objects that can be budgeted.
 */ 
require_once('_securityCheck.php');

class OrganizationBudgetElementMain extends BudgetElement {

  public $id;
  public $_sec_BudgetSynthesis;
  // For select 'year' of synthesis
  public $_byMet_periodYear;
  // For display message 'Budget element not exist
  public $_spe_OrganizationBudgetElementMsg;
  
  public $_tab_3_1_smallLabel = array('idle','idleDate', 'empty',
                                      'idStatus');
  public $idle;
  public $idleDateTime;
  public $_spe_buttonsActionBudgetElement;
  
  public $year;
    
  // Database fields of Budget Element
  // Are 'hidden'
  public $budgetWork;
  public $budgetCost;
  public $expenseBudgetAmount;
  public $totalBudgetCost;

  public $_tab_5_3_smallLabel = array('work','cost','expense','totalCost','reassessed',
                                      'idBudget','daughters','projects');
  // Fields of Budget Element issued of database fields
  // Budget Elements Row
  public $_byMet_budgetWork;
  public $_byMet_budgetCost;
  public $_byMet_expenseBudgetAmount;
  public $_byMet_totalBudgetCost;  
// END ADD BY Marc TABARY - 2017-03-07 - PERIODIC YEAR BUDGET ELEMENT
  public $_void_15;

// _byMet_ : Allows to display the field without sql query and $_fieldsFromFunction definition
// The value is set by a method of this class, on construct of it or any class that call the method
// Here : OrganizationMain.construct call the setDaughtersBudgetElementAndPlanningElement() method of this class
  // Daughters elements Rows
  public $_byMet_daughtersBudgetWork;  
  public $_byMet_daughtersBudgetCost;
  public $_byMet_daughtersBudgetExpenseAmount;
  public $_byMet_daughtersBudgetTotalCost;
  public $_void_25;
  
  // Progress Projects vs Budget Element Row
  public $_byMet_projectProgressWorkPct;
  public $_byMet_projectProgressCostPct;
  public $_byMet_projectProgressExpensePct;
  public $_byMet_projectProgressTotalCostPct;
  public $_byMet_projectProgressPlannedPct;
  // ----------------------------------------------------

  // ---------------------------------------------------------------------------
  public $_sec_synthesis;
  
  public $_tab_5_4_smallLabel = array('validated','assigned','real','left','reassessed',
                                      'work','cost','expense','totalCost');
  // Work row
  public $validatedWork;
  public $assignedWork;
  public $realWork;
  public $leftWork;
  public $plannedWork;
  // Cost row
  public $validatedCost;
  public $assignedCost;
  public $realCost;
  public $leftCost;
  public $plannedCost;
  // Expense row  
  public $expenseValidatedAmount;
  public $expenseAssignedAmount;
  public $expenseRealAmount;
  public $expenseLeftAmount;
  public $expensePlannedAmount;
  // total row
  public $totalValidatedCost;
  public $totalAssignedCost;
  public $totalRealCost;
  public $totalLeftCost;
  public $totalPlannedCost;
  
  public $_nbColMax=3;

  public $reserveAmount;
  public $refType;
  public $refId;
  public $refName;
  public $topId;
  public $topRefType;
  public $topRefId;
  public $elementary;
  
  private static $_fieldsAttributes=array(
      "id"=>"hidden",
      "year"=>"hidden,forceExport", 
      "reserveAmount"=>"hidden", 
      "budgetWork"=>"hiddenforce,forceExport", 
      "budgetCost"=>"hiddenforce,forceExport", 
      "expenseBudgetAmount"=>"hiddenforce,forceExport", 
      "totalBudgetCost"=>"hiddenforce,forceExport,noImport", 
      "elementary"=>"hidden",
      "idle"=>"readonly,forceExport", 
      "idleDateTime"=>"readonly,forceExport", 
      "_byMet_periodYear"=>"noImport,superforceInput,title",
      "refType"=>"hidden",
      "refId"=>"hidden",
      "refName"=>"hidden",
      "progress"=>"display,noImport",
      "topId"=>"hidden",
      "topRefType"=>"hidden",
      "topRefId"=>"hidden",
      "validatedWork"=>"readonly,noImport,forceExport", 
      "assignedWork"=>"readonly,noImport,forceExport", 
      "realWork"=>"readonly,noImport,forceExport", 
      "leftWork"=>"readonly,noImport,forceExport", 
      "plannedWork"=>"readonly,noImport,forceExport", 
      "validatedCost"=>"readonly,noImport,forceExport",
      "assignedCost"=>"readonly,noImport,forceExport", 
      "realCost"=>"readonly,noImport,forceExport", 
      "leftCost"=>"readonly,noImport,forceExport", 
      "plannedCost"=>"readonly,noImport,forceExport", 
      "expenseAssignedAmount"=>"readonly,noImport,forceExport", 
      "expensePlannedAmount"=>"readonly,noImport,forceExport", 
      "expenseRealAmount"=>"readonly,noImport,forceExport",
      "expenseLeftAmount"=>"readonly,noImport,forceExport", 
      "expenseValidatedAmount"=>"readonly,noImport,forceExport", 
      "alertOverPct"=>"title,noImport", 
      "warningOverPct"=>"title,noImport", 
      "okUnderPct"=>"title,noImport", 
      "_byMet_daughtersBudgetWork"=>"readonly,noImport", 
      "_byMet_daughtersBudgetCost"=>"readonly,noImport", 
      "_byMet_daughtersBudgetExpenseAmount"=>"readonly,noImport", 
      "_byMet_daughtersBudgetTotalCost"=>"readonly,noImport", 
      "_byMet_projectProgressWorkPct"=>"readonly,noImport,title,alertOver100warningOver080okUnder050",
      "_byMet_projectProgressCostPct"=>"readonly,noImport,title,alertOver100warningOver080okUnder050", 
      "_byMet_projectProgressExpensePct"=>"readonly,noImport,title,alertOver100warningOver080okUnder050", 
      "_byMet_projectProgressTotalCostPct"=>"readonly,noImport,title,alertOver100warningOver080okUnder050", 
      "_byMet_projectProgressPlannedPct"=>"readonly,noImport,title,alertOver100warningOver080okUnder050", 
      "totalValidatedCost"=>"readonly,noImport,forceExport", 
      "totalAssignedCost"=>"readonly,noImport,forceExport", 
      "totalRealCost"=>"readonly,noImport,forceExport", 
      "totalLeftCost"=>"readonly,noImport,forceExport", 
      "totalPlannedCost"=>"readonly,noImport,forceExport", 
      "totalPlannedCost"=>"readonly,noImport,forceExport", 
      "done"=>"readonly,noImport",
      "cancelled"=>"readonly,noImport",
      "_spe_OrganizationBudgetElementMsg"=>"readonlyforce,drawforce"
  );
  
  private static $_colCaptionTransposition = array(
      '_byMet_periodYear'=>'budgetPeriod',
  );
  // For each field that you want to draw as spinner
  private static $_spinnersAttributes = array(
      'year'=>'min:2000,max:2100,step:1',
      '_byMet_periodYear'=>'min:2000,max:2100,step:1'
      );  

  // Fields list that must be disabled when something changes on form detail
  // getStaticDisabledFieldsOnChange must be implemented on this class
  private static $_disabledFieldsOnChange = array(
      '_byMet_periodYear',
      '_spe_buttonsActionBudgetElement'
  );
  
  private static $_databaseCriteria = array('year'=>'0');
  
  
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    // It's not a very good practice, but it's an 'effective' solution
    if (RequestHandler::isCodeSet('OrganizationBudgetPeriod')) {
      $this->_byMet_periodYear = RequestHandler::getValue('OrganizationBudgetPeriod');
    } else {
      if(sessionValueExists('OrganizationBudgetElementDate')){
          $this->_byMet_periodYear = getSessionValue('OrganizationBudgetElementDate');
          if(!$this->_byMet_periodYear)$this->_byMet_periodYear = date('Y');
      }else{  
        $this->_byMet_periodYear = date('Y');
      }
    }
    $this->setYearPeriod($this->_byMet_periodYear); 
  }
  
  /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    if($colName !='_byMet_periodYear') {
        $colScript = parent::getValidationScript($colName);
    } else {
        // Retrieve min, max value
        // Objective : Do nothing if value, isn't in min, max
        // I don't find how to dismiss direct value input with dojo.NumberSpinner
        // See anomaly in calendar when you delete a digit in spinner year.
        $min = 2000;
        $max = 2100;
        if (isset(self::$_spinnersAttributes)) {
            if (pq_array_key_exists($colName, self::$_spinnersAttributes)) {
                $spinnerProps = pq_explode(',',self::$_spinnersAttributes[$colName]);
                foreach($spinnerProps as $spinnerAttr) {
                    $spinnerNameAndValue = pq_explode(':', $spinnerAttr);
                    if(count($spinnerNameAndValue)==2) {
                        switch(pq_strtolower($spinnerNameAndValue[0])) {
                            case 'min' : 
                                $min=(intval($spinnerNameAndValue[1])?$spinnerNameAndValue[1]:0);
                                break;
                            case 'max' :
                                $max=(intval($spinnerNameAndValue[1])?$spinnerNameAndValue[1]:0);
                                break;
                        }
                    }
                }
                // min > max ==> invert
                if ($min>$max) {
                    $temp=$max;
                    $max=$min;
                    $min=$temp;
                }                
            } else {
                $min = 2000;
                $max = 2100;
            }
            
        }
        
        $colScript = '
<script type="dojo/on" data-dojo-event="change" args="event">if (isEditingKey(event)) {periodChanged(this);}
function periodChanged(theId) {
  var periodYear = theId.get("value");
  saveDataToSession("OrganizationBudgetElementDate",periodYear);
  if (waitingForReply) {
    showInfo(i18n("alertOngoingQuery"));
    return true;
  }
  if (periodYear>='.$min.' && periodYear<='.$max.') {
//      var theMsg = document.getElementById("_spe_OrganizationBudgetElementMsg");
//      if (theMsg != null) {
//        theMsg.style.visibility = "visible";
//        theMsg.innerHTML = "'.i18n('msgCalculationInProgress').'";
//        theMsg.className = "messageOK";
//        theMsg.style.textAlign = "center";
//      }
      loadContent("objectDetail.php?OrganizationBudgetPeriod="+periodYear, "detailDiv", "listForm");
  }
}
</script>';
    }
    return $colScript;

    }
  
// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
    
  /** ==========================================================================
   * Return the generic disabledFieldOnChange
   * @return Array the generic $_disabledFieldOnChange
   */
  protected function getStaticDisabledFieldsOnChange() {
      if(!isset(self::$_disabledFieldsOnChange)) {return array();}
      return self::$_disabledFieldsOnChange;      
  }
  
  /** ==========================================================================
   * Return the generic spinnerAttributes
   * @return Array the generic $_spinnerAttributes
   */
  protected function getStaticSpinnersAttributes() {
      if(!isset(self::$_spinnersAttributes)) {return array();}
      return self::$_spinnersAttributes;
  }
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    if(!isset(self::$_fieldsAttributes)) {return array();}
    return self::$_fieldsAttributes;
  }
  /** ========================================================================
   * Return the specific database criteria
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseCriteria() {
    if(!isset(self::$_databaseCriteria)) {return array();}
    return self::$_databaseCriteria;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    if(!isset(self::$_colCaptionTransposition)) {return array();}
    return self::$_colCaptionTransposition;
}

  /** =============================================================
   * Set the budget element's year db criteria
   * @param int year that served of criteria
   */
  public function setYearPeriod($year) {
      if (!isset(self::$_databaseCriteria)) {
        self::$_databaseCriteria=array();
      }
      //$dbCrit = self::$_databaseCriteria;
      //if(pq_array_key_exists('year', $dbCrit)) {
      self::$_databaseCriteria['year'] = $year;
      //}
  }

  public function hideSynthesisBudgetAndProjectElement($hide=false) {
// ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    if(!Module::isModuleActive('moduleBudgetFunctionOfOrga')) {  
      foreach($this as $fieldName=>$value) {
          switch($fieldName) {
              case '_byMet_budgetWork' :
              case '_byMet_budgetCost' :
              case '_byMet_expenseBudgetAmount' :
              case '_byMet_totalBudgetCost' :    
              case '_byMet_daughtersBudgetWork' :
              case '_byMet_daughtersBudgetCost' :
              case '_byMet_daughtersBudgetExpenseAmount' :    
              case '_byMet_daughtersBudgetTotalCost' :
              case '_byMet_projectProgressWorkPct' :
              case '_byMet_projectProgressCostPct' :
              case '_byMet_projectProgressExpensePct' :
              case '_byMet_projectProgressTotalCostPct' :
              case '_byMet_projectProgressPlannedPct' :
              case 'validatedWork' :
              case 'assignedWork' :
              case 'realWork' :
              case 'leftWork' :
              case 'plannedWork' :
              case 'validatedCost' :
              case 'assignedCost' :
              case 'realCost' :
              case 'leftCost' :
              case 'plannedCost' :
              case 'expenseValidatedAmount' :
              case 'expenseAssignedAmount' :
              case 'expenseRealAmount' :
              case 'expenseLeftAmount' :
              case 'expensePlannedAmount' :
              case 'totalValidatedCost' :
              case 'totalAssignedCost' :
              case 'totalRealCost' :
              case 'totalLeftCost' :
              case 'totalPlannedCost' :
              case 'idle' :
              case 'idleDateTime' :
              case '_sec_BudgetSynthesis' :
                $newFieldAttributes = "hiddenforce,noList,notInFilter";
                self::$_fieldsAttributes[$fieldName] = $newFieldAttributes;                  
                break;
          }
      }  
      return;        
    }
// END ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
      
      
      foreach($this as $fieldName=>$value) {
          switch($fieldName) {
              case '_byMet_budgetWork' :
              case '_byMet_budgetCost' :
              case '_byMet_expenseBudgetAmount' :
              case '_byMet_totalBudgetCost' :    
              case '_byMet_daughtersBudgetWork' :
              case '_byMet_daughtersBudgetCost' :
              case '_byMet_daughtersBudgetExpenseAmount' :    
              case '_byMet_daughtersBudgetTotalCost' :
              case '_byMet_projectProgressWorkPct' :
              case '_byMet_projectProgressCostPct' :
              case '_byMet_projectProgressExpensePct' :
              case '_byMet_projectProgressTotalCostPct' :
              case '_byMet_projectProgressPlannedPct' :
              case 'validatedWork' :
              case 'assignedWork' :
              case 'realWork' :
              case 'leftWork' :
              case 'plannedWork' :
              case 'validatedCost' :
              case 'assignedCost' :
              case 'realCost' :
              case 'leftCost' :
              case 'plannedCost' :
              case 'expenseValidatedAmount' :
              case 'expenseAssignedAmount' :
              case 'expenseRealAmount' :
              case 'expenseLeftAmount' :
              case 'expensePlannedAmount' :
              case 'totalValidatedCost' :
              case 'totalAssignedCost' :
              case 'totalRealCost' :
              case 'totalLeftCost' :
              case 'totalPlannedCost' :
              case 'idle' :
              case 'idleDateTime' :
                  if(pq_array_key_exists($fieldName, self::$_fieldsAttributes)) {
                    $values = self::$_fieldsAttributes[$fieldName];
                    $fieldAttributes = pq_explode(',',$values);
                    $newFieldAttributes = '';
                    foreach ($fieldAttributes as $attr) {
                        switch($attr) {
                            case 'readonly' :
                            case 'readonlyforce' :
                            case 'hidden' :
                            case 'hiddenforce' :
                                $newFieldAttributes .= ($hide?"hiddenforce":"readonlyforce").',';
                                break;
                            default :
                                $newFieldAttributes .= $attr.',';
                                break;
                        }
                    }
                    if (pq_substr($newFieldAttributes,-1,1)==',') {
                        $newFieldAttributes=pq_substr($newFieldAttributes,0,-1);
                    }
                } else {
                        $newFieldAttributes = ($hide?"hiddenforce":"readonlyforce").',';                    
                }
                self::$_fieldsAttributes[$fieldName] = $newFieldAttributes;                  
                break;
          }
      }
      
  }
      
  /** ========================================================================
   * Hide or show the field '_spe_OrganizationBudgetElementMsg
   * @param boolean $hide : True to hide the message 'OrganizationBudgetElementMsg'
   */
  public function hideOrganizationBudgetElementMsg($hide=false) {
      $fieldAttributes = self::$_fieldsAttributes['_spe_OrganizationBudgetElementMsg'];
      $fieldAttribute = pq_explode(',',$fieldAttributes);
      $newFieldAttributes = '';
      foreach ($fieldAttribute as $attr) {
          switch($attr) {
              case 'readonly' :
              case 'readonlyforce' :
              case 'hidden' :
              case 'hiddenforce' :
                  $newFieldAttributes .= ($hide?"hiddenforce":"readonlyforce").',';
                  break;
              default :
                  $newFieldAttributes .= $attr.',';
                  break;
          }
      }
      if ($newFieldAttributes and pq_substr($newFieldAttributes,-1,1)==',') {
          $newFieldAttributes=pq_substr($newFieldAttributes,0,-1);
      }
      self::$_fieldsAttributes['_spe_OrganizationBudgetElementMsg'] = $newFieldAttributes;
      
      if($hide) {
          $this->_tab_3_1_smallLabel = array('idle','idleDate','empty','idStatus');
      } else {
          $this->_tab_3_1_smallLabel = array('empty','empty','empty','empty');
      }
  }
  
  public function setWorkCostExpenseTotalCostBudgetElement() {
      $this->_byMet_budgetWork = $this->budgetWork;
      $this->_byMet_budgetCost = $this->budgetCost;
      $this->_byMet_expenseBudgetAmount = $this->expenseBudgetAmount;
      $this->_byMet_totalBudgetCost = $this->totalBudgetCost;
  }
  
  /** ==========================================================================
   * Extends save functionality to implement update toIp
   * Triggers parent::save() to run defaut functionality in the end.
   * @return String the result of parent::save() function
   */
  public function save() {
    $old=$this->getOld();
    if ($this->id== NULL or pq_trim($this->id)=='') {
        // Initialize year of the new organization's budget element to current year
        $this->year = date('Y');
    } else {
        // Year change => Due to import
        if ($this->year != $old->year) {
            // Search of BudgetElement with $this->year
            $crit = array('refId'=>$this->refId,
                          'refType'=>'Organization',
                          'year'=>$this->year
                         );
            $bE = new BudgetElement();
            $listBe = $bE->getSqlElementsFromCriteria($crit,false,null,null,true,true);
            if(count($listBe)>0) {
                // Find existing BudgetElement
                foreach ($listBe as $bE) {
                    $bE->refName = $this->refName;
                    $bE->budgetWork = $this->budgetWork;
                    $bE->budgetCost = $this->budgetCost;
                    $bE->expenseBudgetAmount = $this->expenseBudgetAmount;
                    $bE->totalBudgetCost = $bE->budgetCost + $bE->expenseBudgetAmount;
                    $result=$bE->save();
                }
                return $result;
            }
            // Not Found => Create it
            $this->id = null;
            $theYear=$this->year;
            $result=parent::save();
            // Must do that due to $_databeCriteria initilization with current date.
            $this->year = $theYear;
            $this->simpleSave();
            // Force calculation of BudgetElement's project informations
            $bE = new BudgetElement($this->id);
            $orga=new Organization($this->refId,true);
            $orga->updateBudgetElementSynthesis($bE);
            return $result;
        }
    }        
    return parent::save();
  }  

  /** ==========================================================================
   * Draw 
   * @param string $item : The item name
   * @return string
   */
  private function drawActionsButtonsGroup($item,$readOnly) {
// ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    if(!Module::isModuleActive('moduleBudgetFunctionOfOrga')) {
        return;
    }
// END ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    global $print;
    
    $scope = 'Organization';
    $result='';
    
    if($print or $item<>'buttonsActionBudgetElement' or $readOnly) {return '';}

    // Visibility
    $wcVisibility= $this->_workVisibility.$this->_costVisibility;
    
    if($this->id===null or pq_trim($this->id)=='') { # ADD => If not exists
        if ($wcVisibility!='NONO') { # and visibility on cost OR work
            // Parameters :
            // 1. The class (to be more generic)
            // 2. The id of Organization (like refId => To be homogeneous with change
            // 3. The id of BudgElement (0 = Add)
            // 4. The periodicYear
            // 5. The scope (to be more generic)
            $result .= ' <a onClick="addBudgetElement(\'' 
                            . get_class($this) 
                            . '\',\'' . htmlEncode($this->refId)  
                            . '\',\'' . 0  
                            . '\',\'' . htmlEncode($this->_byMet_periodYear)  
                            . '\',\'' . $scope
                            . '\');" title="' . i18n('addBudgetElement') . '" > '.formatSmallButton('Add').'</a>';
        }
    } else {
        if($this->idle==0) { # EDIT => If idle = 0
            $closeButton = 'Close';
            if($wcVisibility!='NONO') {#  and visibility on cost OR work
                // Parameters :
                // 1. The class (to be more generic)
                // 2. The id of Organization (refId)
                // 3. The id of BudgetElement
                // 4. The year
                // 5. budgetWork
                // 6. budgetCost
                // 7. expenseBudgetAmount
                $result .= ' <a onClick="changeBudgetElement(\'' 
                                . get_class($this) 
                                . '\',\'' . htmlEncode($this->refId)  
                                . '\',\'' . htmlEncode($this->id)  
                                . '\',\'' . htmlEncode($this->year)  
                                . '\',\'' . htmlEncode($this->budgetWork)  
                                . '\',\'' . htmlEncode($this->budgetCost)  
                                . '\',\'' . htmlEncode($this->expenseBudgetAmount)
                                . '\');" title="' . i18n('editBudgetElement') . '" > '.formatSmallButton('Edit').'</a>';
            }
        } else {$closeButton = 'UnClose';}
        if($this->year!=date('Y')) { # REMOVE => Only if year is different of current year.
        // Parameters :
        // 1. The class (to be more generic)
        // 2. The id of Organization (RefId)
        // 3. The id
            $result .= ' <a onClick="removeBudgetElement(\'' 
                            . get_class($this) 
                            . '\',\'' . htmlEncode($this->refId) 
                            . '\',\'' . htmlEncode($this->id) 
                            . '\',\'' . htmlEncode($this->year) 
                            . '\');" title="' . i18n('removeBudgetElement') . '" > '.formatSmallButton('Remove').'</a>';
        }
//        if(($this->year==date('Y') and $this->idle==1) or $this->year!=date('Y')) { # CLOSE => Only if year is different of current year
            # CLOSE OR UNCLOSE
            // Parameters :
            // 1. The class (to be more generic)
            // 2. The id of Organization (RefId)
            // 2. The id
            // 3. The idle        
            $result .= ' <a onClick="closeUncloseBudgetElement(\'' 
                            . get_class($this) 
                            . '\',\'' . htmlEncode($this->refId) 
                            . '\',\'' . htmlEncode($this->id) 
                            . '\',\'' . htmlEncode($this->idle) 
                            . '\',\'' . htmlEncode($this->year) 
                            . '\');" title="' . i18n(($this->idle?'uncloseBudgetElement':'closeBudgetElement')) . '" > '.formatSmallButton($closeButton).'</a>';
//        }
    }
    if ($result!='') {
        $result='<div id="id__'.$item.'" class="assignData smallButtonsGroup">'.$result;
        $result .='</div>';
    }
    return $result;
  }
  
  /** ==========================================================================
   * Draw the specific fields of this class
   * @param string $item : fields name to draw
   */
  public function drawSpecificItem($item,$readOnly=true) {
// ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    if(!Module::isModuleActive('moduleBudgetFunctionOfOrga')) {
        return;
    }
// END ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
      switch($item) {
          // Draw the message that say if BudgetElement exits or not
          case 'OrganizationBudgetElementMsg' :
              if(pq_strpos($this->getFieldAttributes('_spe_'.$item),'hidden')!== false) {
                  $hidden='hidden';                  
              } else {
                  $hidden='';
              }
              $result = '<div '.$hidden.' id="_spe_'.$item.'" name = "_spe_'.$item.'" class="messageDataValue messageWARNING">'.i18n('noBudgetForThisPeriod').'</div>';
              break;
          // Draw the group of action's buttons on BudgetElement
          case 'buttonsActionBudgetElement' :
              $result = $this->drawActionsButtonsGroup($item,$readOnly);
              break;
          default :
              $result='';
              break;
      }
      return $result;
  }
  
  /** =============================================================
   * Set the 
   *   - subOrganization budget elements ie :
   *        substracts sub-BudgetElement to this BudgetElement
   *        for the following elements :
   *            budgetWork, budgetCost, budgetExpense, totalBudgetCost
   *   - progress elements ie :
   *        % between projets element and organization bugdet element
   *        for the following elements :
   *           Work     : % budgetElement.realWork vs budgetElement.budgetWork
   *           Cost     : % budgetElement.realCost vs budgetElement.budgetCost
   *           Expense  : % budgetElement.expenseRealAmount vs budgetElement.expenseBudgetAmount
   *           Total    : % budgetElement.totalRealCost vs budgetElement.totalBudgetCost
   *           Planned  : % budgetElement.plannedCost vs budgetElement.totalBudgetCost
   */
  public function setDaughtersBudgetElementAndPlanningElement() {

      
      if ($this->id===NULL or pq_trim($this->id)=="" or 
// ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
          !Module::isModuleActive('moduleBudgetFunctionOfOrga')    
// END ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
         ) {
          $this->_byMet_daughtersBudgetWork=0;
          $this->_byMet_daughtersBudgetCost=0;
          $this->_byMet_daughtersBudgetExpenseAmount=0;
          $this->_byMet_daughtersBudgetTotalCost=0;
          $this->_byMet_projectProgressWorkPct=0;
          $this->_byMet_projectProgressCostPct=0;
          $this->_byMet_projectProgressExpensePct=0;
          $this->_byMet_projectProgressTotalCostPct=0;
          $this->_byMet_projectProgressPlannedPct=0;  
          return;
      }
      $this->_byMet_daughtersBudgetWork = $this->budgetWork;
      $this->_byMet_daughtersBudgetCost = $this->budgetCost;
      $this->_byMet_daughtersBudgetExpenseAmount = $this->expenseBudgetAmount;
      $this->_byMet_daughtersBudgetTotalCost = $this->totalBudgetCost;
      if ($this->budgetWork==0) {
          $this->_byMet_projectProgressWorkPct=null;
      } else {
          $this->_byMet_projectProgressWorkPct=round(($this->realWork/$this->budgetWork)*100);                
      }
      if ($this->budgetCost==0) {
          $this->_byMet_projectProgressCostPct=null;
      } else {
          $this->_byMet_projectProgressCostPct=round(($this->realCost/$this->budgetCost)*100);                
      }
      if ($this->expenseBudgetAmount==0) {
          $this->_byMet_projectProgressExpensePct=null;
      } else {
          $this->_byMet_projectProgressExpensePct=round(($this->expenseRealAmount/$this->expenseBudgetAmount)*100);                
      }
      if ($this->totalBudgetCost==0) {
          $this->_byMet_projectProgressTotalCostPct=null;
          $this->_byMet_projectProgressPlannedPct=null;
      } else {
          $this->_byMet_projectProgressTotalCostPct=round(($this->totalRealCost/$this->totalBudgetCost)*100);                
          $this->_byMet_projectProgressPlannedPct=round(($this->plannedCost/$this->totalBudgetCost)*100);                
      }
      
      // Retrieve the sub-BudgetElements
      $theSubBudgetsElement = $this->getSubBudgetElement();
      // For each sub-BudgetElements, substracts parent BudgetElement, value of sub-BudgetEment
      foreach($theSubBudgetsElement as $aSubBudgetEment) {
          $this->_byMet_daughtersBudgetWork-= $aSubBudgetEment->budgetWork;
          $this->_byMet_daughtersBudgetCost-= $aSubBudgetEment->budgetCost;
          $this->_byMet_daughtersBudgetExpenseAmount-= $aSubBudgetEment->expenseBudgetAmount;
          $this->_byMet_daughtersBudgetTotalCost-= $aSubBudgetEment->totalBudgetCost;
      }
  }
            
  private function getSubBudgetElement() {
// ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    if (!Module::isModuleActive('moduleBudgetFunctionOfOrga')) {
        return array();
    }    
// END ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT      
    $critOrga['idOrganization']=$this->refId;
    $critOrga['idle']='0';
    
    $myOrga = new Organization();
    $subOrganizations=$myOrga->getSqlElementsFromCriteria($critOrga, false,null,null,null,true) ;
    if (count($subOrganizations)==0) { return array();}      
    
    $theBudgetsElement = array();
    $theFirstBudgetsElement = array();
    $theSubOrga = SqlElement::transformObjSqlElementInArrayKeyName($subOrganizations);
    
//     foreach($theSubOrga as $key => $name) {
//         $crit['refType'] = 'Organization';
//         $crit['refId'] = $key;
//         $crit['year'] = $this->year;
//         $crit['idle'] = '0';
//         $theFirstBudgetsElement = $this->getSqlElementsFromCriteria($crit, false,null,null,null,true,true);
//     }

    foreach ($subOrganizations as $subOrga) {
        $recursiveList=$subOrga->getRecursiveSubOrganizationsFlatList(true, true);
        foreach($recursiveList as $key => $name) {
            $crit['refType'] = 'Organization';
            $crit['refId'] = $key;
            $crit['year'] = $this->year;
            $crit['idle'] = '0';
            $oBe =$this->getSqlElementsFromCriteria($crit, false,null,null,null,true);
            if ($oBe!=null) {
                $theBudgetsElement = array_merge($theBudgetsElement, $oBe);
            }
        }      
    }
//    $theBudgetsElement = array_merge($theBudgetsElement, $theFirstBudgetsElement);
    return $theBudgetsElement;
  }

  
  /** =======================================================
   * Get the parent organization of this budget element
   * @return \Organization
   */      
  public function getOrganizationParent() {
      $myOrga = new Organization($this->refId);
      if ($myOrga->idOrganization === null) {return null;}
      $myOrgaParent = new Organization($myOrga->idOrganization);
      return $myOrgaParent;
  }

  public function setValueOfAlertOverWarningOverOkUnder($alertOver=100, $warningOver=80, $okUnder=50) {
    $XXX=sprintf("%'.03d\n", $alertOver);
    $YYY=sprintf("%'.03d\n", $warningOver);
    $ZZZ=sprintf("%'.03d\n", $okUnder);
    
    $fieldsAttributes = self::$_fieldsAttributes;
    foreach($fieldsAttributes as $fieldName=>$value) {
        if (pq_strpos($value, 'alertOver') !== false or 
              pq_strpos($value, 'warningOver') !== false or
              pq_strpos($value, 'okUnder') !== false
            ) {
            // alertOver
            $posAWO = pq_strpos($value, 'alertOver');
            if ($posAWO and $alertOver!=0) {
                $overValue = pq_substr($value,$posAWO+9,3);
                $value = pq_str_replace('alertOver'.$overValue, 'alertOver'.$XXX, $value);
            }
            
            // warningOver
            $posAWO = pq_strpos($value, 'warningOver');
            if ($posAWO and $warningOver!=0) {
                $overValue = pq_substr($value,$posAWO+11,3);
                $value = pq_str_replace('warningOver'.$overValue, 'warningOver'.$YYY, $value);
            }
            
            // okUnder
            $posAWO = pq_strpos($value, 'okUnder');
            if ($posAWO and $okUnder!=0) {
                $overValue = pq_substr($value,$posAWO+7,3);
                $value = pq_str_replace('okUnder'.$overValue, 'okUnder'.$ZZZ, $value);
            }
        }
        // Set the attributes
        self::$_fieldsAttributes[$fieldName]=$value;
    }
  }    

  
  /** =========================================================
   * Hide all fields those have :
   *  - $_fieldsAttributes defined
   *  - Cost, Work at the name's end
   *  - Amount (case insensitive) in the name
   * @return void
   */
  private function hideWorkCost() {
    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false ) {
                continue;
            }
            
            if (pq_substr($name,-4,4)==='Cost' or
                pq_substr($name,-4,4)==='Work' or
                pq_strtolower(pq_substr($name,-6,6))==='amount') {
                    if (pq_strpos($value,'readonly')!==false) {
                        self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                    } else {
                        if (pq_strpos($value,'hidden')===false) {
                            self::$_fieldsAttributes[$name] = $value.',hidden';
                        }
                    }
            }
        }
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';

    return;
      
      
/* Babynus : next code no more used, same things done generatically by previous code      
// ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['budgetWork']='hidden';
// END ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['validatedWork']='hidden';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';
    self::$_fieldsAttributes['plannedWork']='hidden';
// ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['budgetCost']='hidden';
// END ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['validatedCost']='hidden';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
    self::$_fieldsAttributes['plannedCost']='hidden';
// ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['expenseBudgetAmount']='hidden';
// END ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['expenseValidatedAmount']='hidden';
    self::$_fieldsAttributes['expenseAssignedAmount']='hidden';
    self::$_fieldsAttributes['expenseRealAmount']='hidden';
    self::$_fieldsAttributes['expenseLeftAmount']='hidden';
    self::$_fieldsAttributes['expensePlannedAmount']='hidden';
// COMMENT BY Marc TABARY - 2017-02-17 - WORK AND COST VISIBILITY      
//    self::$_fieldsAttributes['reserveAmount']='hidden';
// END COMMENT BY Marc TABARY - 2017-02-17 - WORK AND COST VISIBILITY      
// ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['totalBudgetCost']='hidden';
// END ADD BY Marc TABARY - 2017-02-27 - ORGANIZATION BUDGET      
    self::$_fieldsAttributes['totalValidatedCost']='hidden';
    self::$_fieldsAttributes['totalAssignedCost']='hidden';
    self::$_fieldsAttributes['totalRealCost']='hidden';
    self::$_fieldsAttributes['totalLeftCost']='hidden';
    self::$_fieldsAttributes['totalPlannedCost']='hidden';
    */
  }

  /** =========================================================
   * For fields those have $_fieldsAttributes defined :
   *  - Show :
   *    - Cost, Work at the name's end
   *    - Amount (case insensitive) in the name
   *  - Allows enter value :
   *    - budget (case insensitive) and not total (case insensitive) in the name
   * @return void
   */
  private function showWorkCost() {
    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // Budgets : Allows input its except for total
            if (pq_strpos(pq_strtolower($name),'budget')!==false and pq_strpos(pq_strtolower($name),'total')===false) {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
            } else {
                // Cost - Amount - Work are readonly
                if (pq_substr($name,-4,4)==='Cost' or
                    pq_substr($name,-4,4)==='Work' or
                    pq_strtolower(pq_substr($name,-6,6))==='amount') {
                        if (pq_strpos($value,'hidden')!==false) {
                            self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                        } else {
                            if (pq_strpos($value,'readonly')===false) {
                                self::$_fieldsAttributes[$name] = $value.',readonly';
                            }
                        }
                }
            }
        }
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';

    return;
  }
  
  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value :
   *    - budget (case insensitive) and not total (case insensitive) in the name
   *  - Show :
   *    - validated (case insensitive) in the name
   *  - Hide :
   *    - Cost, Work in the name's end
   *    - amount (cas insensitive) in the name
   * @return void
   */
  private function showValidated() {

    
    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // total budget : show
            if (pq_strpos(pq_strtolower($name),'total')!== false and pq_strpos(pq_strtolower($name),'budget')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Budgets : Allows input its except for total
            if (pq_strpos(pq_strtolower($name),'budget')!==false and pq_strpos(pq_strtolower($name),'total')===false) {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Validated : Show
            if (pq_strpos(pq_strtolower($name),'validated')!== false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Cost, Work, amount : Hide
            if (pq_strpos(pq_strtolower($name),'amount')!== false or
                pq_substr($name,-4,4)==='Cost' or
                pq_substr($name,-4,4)==='Work') {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';

  }

  
  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value :
   *    - budget (case insensitive) in the name and Work at the name's end
   *  - Show :
   *    - Work in the name's end
   *  - Hide :
   *    - Cost in the name's end
   *    - amount (case insensitive) in the name
   * @return void
   */
  private function showOnlyWork() {

    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // Budgets : Allows input only for work
            if (pq_strpos(pq_strtolower($name),'budget')!==false and pq_substr($name,-4,4)==='Work') {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Work : Show
            if (pq_substr($name,-4,4)==='Work') {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Cost, amount : Hide
            if (pq_strpos(pq_strtolower($name),'amount')!== false or
                pq_substr($name,-4,4)==='Cost') {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';
  }
  
  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value, except total (case insensitive) in the name:
   *    - budget (case insensitive) in the name and ( Cost at the name's end or amount (case insensitive) in the name)
   *  - Show :
   *    - Cost in the name's end and amount (case insensitive) in the name
   *  - Hide :
   *    - Work in the name's end
   * @return void
   */
  private function showOnlyCost() {

    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // total budget : show
            if (pq_strpos(pq_strtolower($name),'total')!== false and pq_strpos(pq_strtolower($name),'budget')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Budgets : Allows input only for cost and amount (except total)
            if (pq_strpos(pq_strtolower($name),'budget')!==false and
                pq_strpos(pq_strtolower($name),'total')===false and  
                (pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false)
               ) {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Cost and amount : Show
            if (pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Work : Hide
            if (pq_substr($name,-4,4)==='Work') {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';
  }

  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value, except total (case insensitive) in the name :
   *    - budget (case insensitive) in the name
   *  - Show :
   *    - Cost in the name's end and amount (case insensitive) in the name
   *    - Work in the name's end and validated (case insensitive) in the name
   *  - Hide :
   *    - Work in the name's end and not validated (case insensitive) in the name
   * @return void
   */
  private function showOnlyValidatedWorkAndAllCost() {

    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // total budget : show
            if (pq_strpos(pq_strtolower($name),'total')!== false and pq_strpos(pq_strtolower($name),'budget')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Budgets : Allows input except total
            if (pq_strpos(pq_strtolower($name),'budget')!==false and
                pq_strpos(pq_strtolower($name),'total')===false) {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Cost and amount : Show
            if (pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // validated Work : Show
            if (pq_substr($name,-4,4)==='Work' and pq_strpos(pq_strtolower($name),'validated')!== false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // not validated Work : Hide
            if (pq_substr($name,-4,4)==='Work' and pq_strpos(pq_strtolower($name),'validated')=== false) {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';
  }

  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value, except total (case insensitive) in the name :
   *    - budget (case insensitive) in the name and not Work at the name's end
   *  - Show :
   *    - Cost in the name's end and amount (case insensitive) in the name and validated (case insensitive) in the name
   *  - Hide :
   *    - Work in the name's end
   *    - Cost in the name's end and amount (case insensitive) in the name and not validated (case insensitive) in the name
   * @return void
   */
  private function hideWorkAndShowValidatedCost() {

    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // total budget : show
            if (pq_strpos(pq_strtolower($name),'total')!== false and pq_strpos(pq_strtolower($name),'budget')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Budgets : Allows input except total and work
            if (pq_strpos(pq_strtolower($name),'budget')!==false and
                pq_strpos(pq_strtolower($name),'total')===false and
                pq_substr($name,-4,4)!=='Work') {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Cost and amount validated : Show
            if ((pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) and
                 pq_strpos(pq_strtolower($name),'validated')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Work : Hide
            if (pq_substr($name,-4,4)==='Work') {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }
                continue;
            }

            // Cost and amount not validated : Hide
            if ((pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) and
                 pq_strpos(pq_strtolower($name),'validated')===false) {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';
  }

  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value, except total (case insensitive) in the name :
   *    - budget (case insensitive) in the name
   *  - Show :
   *    - Cost in the name's end and amount (case insensitive) in the name and validated (case insensitive) in the name
   *    - Work in the name's end
   *  - Hide :
   *    - Cost in the name's end and amount (case insensitive) in the name and not validated (case insensitive) in the name
   * @return void
   */
  private function showAllWorkAndValidatedCost() {

    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // total budget : show
            if (pq_strpos(pq_strtolower($name),'total')!== false and pq_strpos(pq_strtolower($name),'budget')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Budgets : Allows input except total
            if (pq_strpos(pq_strtolower($name),'budget')!==false and
                pq_strpos(pq_strtolower($name),'total')===false) {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Cost and amount validated : Show
            if ((pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) and
                 pq_strpos(pq_strtolower($name),'validated')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Work : Show
            if (pq_substr($name,-4,4)==='Work') {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Cost and amount not validated : Hide
            if ((pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) and
                 pq_strpos(pq_strtolower($name),'validated')===false) {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';
  }
  
  /** ===============================================
   * For fields those have $_fieldsAttributes defined :
   *  - Allows enter value, except total (case insensitive) in the name :
   *    - budget (case insensitive) in the name and Work at the name's end
   *  - Show :
   *    - Work in the name's end and validated (case insensitive) in the name
   *  - Hide :
   *    - Cost in the name's end and amount (case insensitive)
   *    - Work in the name's end and not validated (case insensitive) in the name
   * @return void
   */
  private function showOnlyValidatedWorkAndHideCost() {

    if (isset(self::$_fieldsAttributes)) {
        foreach(self::$_fieldsAttributes as $name => $value) {
            // Do nothing if 'hiddenforce'
            if (pq_strpos(pq_strtolower($value),'hiddenforce')!== false) {
                continue;
            }
            // total budget : hide
            if (pq_strpos(pq_strtolower($name),'total')!== false and pq_strpos(pq_strtolower($name),'budget')!==false) {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }            
                continue;
            }

            // Budgets work : Allows input except total
            if (pq_strpos(pq_strtolower($name),'budget')!==false and
                pq_substr($name,-4,4)==='Work' and    
                pq_strpos(pq_strtolower($name),'total')===false) {
                self::$_fieldsAttributes[$name] = pq_str_replace('readonly', '', $value);
                self::$_fieldsAttributes[$name] = pq_str_replace('hidden', '', $value);
                continue;            
            } 

            // Work validated : Show
            if (pq_substr($name,-4,4)==='Work' and pq_strpos(pq_strtolower($name),'validated')!==false) {
                if (pq_strpos($value,'hidden')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('hidden', 'readonly', $value);
                } else {
                    if (pq_strpos($value,'readonly')===false) {
                        self::$_fieldsAttributes[$name] = $value.',readonly';
                    }
                }
                continue;
            }

            // Cost and amount : Hide
            if (pq_substr($name,-4,4)==='Cost' or pq_strpos(pq_strtolower($name),'amount')!== false) {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }
                continue;
            }

            // Work not validated : Hide
            if (pq_substr($name,-4,4)==='Work' and pq_strpos(pq_strtolower($name),'validated')===false) {
                if (pq_strpos($value,'readonly')!==false) {
                    self::$_fieldsAttributes[$name] = pq_str_replace('readonly', 'hidden', $value);
                } else {
                    if (pq_strpos($value,'hidden')===false) {
                        self::$_fieldsAttributes[$name] = $value.',hidden';
                    }
                }
                continue;
            }
        }    
    }        
    // For the moment, reserveAmount is always hidden
    self::$_fieldsAttributes['reserveAmount'] = 'hidden';
  }

  public function setAttributes() {
    if (!$this->_workVisibility or !$this->_costVisibility) $this->setVisibility();
    $workVisibility=$this->_workVisibility;
    $costVisibility=$this->_costVisibility;
    // ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    if(!Module::isModuleActive('moduleBudgetFunctionOfOrga')) {
      self::$_fieldsAttributes["_sec_synthesis"] = "hidden,noPrint";
      self::$_fieldsAttributes["_byMet_periodYear"] = "hidden,noList,notInFilter";
    }
    // END ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
    if (pq_trim($this->id)) {
      $this->setDaughtersBudgetElementAndPlanningElement();
      $this->setWorkCostExpenseTotalCostBudgetElement();
      // A solution for showing something when BudgetElement
      $this->_tab_3_1_smallLabel = array('idle','idleDate','empty','idStatus');
    } else {
      $this->hideSynthesisBudgetAndProjectElement(true);
      // A solution for showing nothing when no BudgetElement
      $this->_tab_3_1_smallLabel = array('empty','empty','empty','empty');
    }
    $wcVisibility = $workVisibility.$costVisibility;
    switch ($wcVisibility) {
        case "NONO" :
            $this->hideWorkCost();
            break;
        case "NOALL" :
            $this->showOnlyCost();
            break;
        case "NOVAL" :
            $this->hideWorkAndShowValidatedCost();
            break;
        case "ALLALL" :
            $this->showWorkCost();
            break;
        case "ALLNO" :
            $this->showOnlyWork();
            break;
        case "ALLVAL" :
            $this->showAllWorkAndValidatedCost();
            break;
        case "VALVAL" :
            $this->showValidated();
            break;
        case "VALALL" :
            $this->showOnlyValidatedWorkAndAllCost();
            break;
        case "VALNO" :
            $this->showOnlyValidatedWorkAndHideCost();
            break;
        default:
            $this->hideWorkCost();
            break;
    }
    $this->hideOrganizationBudgetElementMsg(($this->id)?true:false);
  }
}?>