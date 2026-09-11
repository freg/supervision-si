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
 * Parameter is a global kind of object for parametring.
 * It may be on user level, on project level or on global level.
 */ 
require_once('_securityCheck.php');
class TodayParameter extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visiblez place 
  public $idUser;
  public $idReport;
  public $idToday;
  public $parameterName;
  public $parameterValue;
  
  public static $staticList=array('Projects','AssignedTasks','ResponsibleTasks','IssuerRequestorTasks','ProjectsTasks');
  public $_noHistory=true; // Will never save history for this object
  
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
// GET VALIDATION SCRIPT
// ============================================================================**********

  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  
  static public function returnReportParameters($report, $includeAllBooleans=false) {
    $result=array();
    $currentWeek=weekNumber(date('Y-m-d'));
    if (pq_strlen($currentWeek)==1) {
      $currentWeek='0' . $currentWeek;
    }
    $currentYear=pq_strftime("%Y") ;
    $currentMonth=pq_strftime("%m") ;
    $listParam=array();
    if(SqlList::getNameFromId('ReportCategory', $report->idReportCategory, false) == 'reportCategoryObjectList'){
      $idReport = $report->id;
      $idReportLayout = pq_substr($report->file, (pq_strpos($report->file, 'reportLayoutId')+15));
      $reportLayoutObjectClass=SqlList::getFieldFromId('ReportLayout', $idReportLayout, 'objectClass');
      if($reportLayoutObjectClass){
        if(property_exists($reportLayoutObjectClass, 'idProject')){
          $reportParam = new ReportParameter();
          $reportParam->idReport = $idReport;
          $reportParam->name = 'idProject';
          $reportParam->paramType = 'projectList';
          $reportParam->sortOrder = 10;
          $reportParam->defaultValue = 'currentProject';
          $listParam[]=$reportParam;
        }
        if(property_exists($reportLayoutObjectClass, 'idResource')){
          $reportParam = new ReportParameter();
          $reportParam->idReport = $idReport;
          $reportParam->name = 'responsible';
          $reportParam->paramType = 'resourceList';
          $reportParam->sortOrder = 10;
          $reportParam->defaultValue = 'currentResource';
          $listParam[]=$reportParam;
        }
        if(property_exists($reportLayoutObjectClass, 'idOrganization')){
          $reportParam = new ReportParameter();
          $reportParam->idReport = $idReport;
          $reportParam->name = 'idOrganization';
          $reportParam->paramType = 'organizationList';
          $reportParam->sortOrder = 10;
          $reportParam->defaultValue = 'currentOrganization';
          $listParam[]=$reportParam;
        }
        if(property_exists($reportLayoutObjectClass, 'idTeam')){
          $reportParam = new ReportParameter();
          $reportParam->idReport = $idReport;
          $reportParam->name = 'idTeam';
          $reportParam->paramType = 'teamList';
          $reportParam->sortOrder = 10;
          $listParam[]=$reportParam;
        }
        if(property_exists($reportLayoutObjectClass, SqlElement::getTypeName($reportLayoutObjectClass))){
          $reportParam = new ReportParameter();
          $reportParam->idReport = $idReport;
          $reportParam->name = SqlElement::getTypeName($reportLayoutObjectClass);
          $reportParam->paramType = SqlElement::getTypeClassName($reportLayoutObjectClass).'List';
          $reportParam->sortOrder = 10;
          $listParam[]=$reportParam;
        }
      }
    }else{
      $param=new ReportParameter();
      $crit=array('idReport'=>$report->id);
      $listParam=$param->getSqlElementsFromCriteria($crit,false,null,'sortOrder');
    }
    
    foreach ($listParam as $param) {
      if ($param->paramType=='week') {
        $result['periodType']='week';
        $result['periodValue']=($param->defaultValue=='currentWeek')?$currentYear . $currentWeek:$param->defaultValue;
        $result['yearSpinner']=pq_substr($result['periodValue'],0,4);
        $result['weekSpinner']=pq_substr($result['periodValue'],4,2);
      } else if ($param->paramType=='month') {
        $result['periodType']='month';
        $result['periodValue']=($param->defaultValue=='currentMonth')?$currentYear . $currentMonth:$param->defaultValue;
        $result['yearSpinner']=pq_substr($result['periodValue'],0,4);
        $result['monthSpinner']=pq_substr($result['periodValue'],4,2);
      } else if ($param->paramType=='year') {
        $result['periodType']='year';
        $result['periodValue']=($param->defaultValue=='currentYear')?$currentYear:$param->defaultValue;
        $result['yearSpinner']=$result['periodValue'];
        $result['monthSpinner']='1';
      } else if ($param->paramType=='date') {
        $result[$param->name]=($param->defaultValue=='today')?date('Y-m-d'):$param->defaultValue;
      } else if ($param->paramType=='periodScale') {
        $result[$param->name]=$param->defaultValue;
      } else if ($param->paramType=='boolean') {
        if ($param->defaultValue=='true') {
        	$result[$param->name]=true;
        } else if ($includeAllBooleans) {
        	$result[$param->name]=$param->defaultValue;
        }
      } else if ($param->paramType=='projectList') {
        $defaultValue='';
        if ($param->defaultValue=='currentProject') {       
          $defaultValue=Project::getSelectedProject(true,true);
        } else if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='productList') {
        $defaultValue='';
        if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='userList') {
        $defaultValue='';
        if ($param->defaultValue=='currentUser') {
          if (sessionUserExists()) {
            $user=getSessionUser();
            $defaultValue=$user->id;
          }
        } else if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='versionList') {
        $defaultValue=$param->defaultValue;
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='testSessionList') {
        $defaultValue=$param->defaultValue;
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='resourceList') {
        $defaultValue='';
        if ($param->defaultValue=='currentResource') {
          if (Project::isSelectedProject()) {
            $user=getSessionUser();
            $defaultValue=$user->id;
          }
        } else if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='requestorList') {
        $defaultValue='';
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='showDetail') {
        $defaultValue='';
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='ticketType') {
        $defaultValue='';
        if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='objectList') {
        $defaultValue='';
        if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else if ($param->paramType=='id') {
        $defaultValue='';
        if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      } else {
        $defaultValue='';
        if ($param->defaultValue) {
          $defaultValue=$param->defaultValue; 
        }
        $result[$param->name]=$defaultValue;
      }
    }
    return $result;
  }
  
  static public function returnTodayReportParameters($today) {
  	$tp=new TodayParameter();
    $tpList=$tp->getSqlElementsFromCriteria(array('idToday'=>$today->id));
    $result=array();
    foreach ($tpList as $tp) {
    	$result[$tp->parameterName]=$tp->parameterValue;
    }
    return $result;
  }
}
?>