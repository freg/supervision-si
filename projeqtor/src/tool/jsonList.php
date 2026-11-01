<?PHP
use PhpOffice\PhpSpreadsheet\Cell\DataType;
/**
 * * COPYRIGHT NOTICE *********************************************************
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
 * FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 * ** DO NOT REMOVE THIS NOTICE ***********************************************
 */

/**
 * ===========================================================================
 * Get the list of objects, in Json format, to display the grid list
 */
require_once "../tool/projeqtor.php";
require_once "../tool/jsonFunctions.php";
session_write_close();
// scriptLog(' ->/tool/jsonList.php');
$type = $_REQUEST ['listType']; // Note: checked against constant values.
$view=(RequestHandler::isCodeSet('actualView'))?RequestHandler::getValue('actualView'):'Filter';
$objectClass = RequestHandler::getClass('objectClass');
if (isset ( $_REQUEST ['critField'] )) {
  $field = $_REQUEST ['critField'];
  Security::checkValidAlphanumeric ( $field );
  if (! isset ( $_REQUEST ['critValue'] )) {
    errorLog ( "incorrect query jonList : critValue is not set but critField set" );
    return;
  }
  if (pq_substr ( $field, 0, 2 ) == 'id' and pq_substr ( $field, 2, 1 ) == pq_strtoupper ( pq_substr ( $field, 2, 1 ) )) {
    if (isset ( $_REQUEST ['critArray'] )) {
      $_REQUEST ['critValue'] = explode ( ',', $_REQUEST ['critValue'] );
      foreach ( $_REQUEST ['critValue'] as $v ) {
        Security::checkValidId ( $v );
      }
    } else {
      if ($field=='idProject' or ($field=='id' and RequestHandler::getValue('dataType')=='idProject')) {
        $idList=pq_explode(',',$_REQUEST ['critValue']);
        foreach($idList as $idP) {
          Security::checkValidId ( $idP);
        }
      } else {
        Security::checkValidId ( $_REQUEST ['critValue'] );
      }
    }
  }
} else if (isset ( $_REQUEST ['critValue'] )) {
  errorLog ( "incorrect query jonList : critValue is set but critField is not set" );
  return;
}
echo '{"identifier":"id",';
echo 'label: "name",';
echo ' "items":[';
// If type = 'list' and $dataType = idResource : execute the listResourceProject type
$required = true; // when directly requesting 'listResourceProject', required is by default
if ($type == 'list' and pq_array_key_exists ( 'dataType', $_REQUEST ) and ($_REQUEST ['dataType'] == 'idResource' or $_REQUEST ['dataType'] == 'idResourceAll'   or $_REQUEST ['dataType'] == 'idAccountable' or $_REQUEST ['dataType'] == 'idResponsible' or pq_substr($_REQUEST ['dataType'],-12)=='__idResource') and pq_array_key_exists ( 'critField', $_REQUEST ) and pq_array_key_exists ( 'critValue', $_REQUEST ) and $_REQUEST ['critField'] == 'idProject') {
  $type = 'listResourceProject';
  $_REQUEST ['idProject'] = $_REQUEST ['critValue']; // This is valid : force idProject to critValue as criFiled=idProject (value has been tested as an id)
  $required = pq_array_key_exists ( 'required', $_REQUEST );
}
if ($type == 'ExpenseDetailType') {
  $type = 'list';
}

if ($type == 'empty') {
  // Emty ;)
} else if ($type == 'object') { // ================================================= OBJECT =====================================================================================
  $objectClass = $_REQUEST ['objectClass'];
  Security::checkValidClass ( $objectClass, 'objectClass' );
  $obj = new $objectClass ();
  ob_start();
  if($view!='MultipleUpadate' and $objectClass=='PlanningElement'){
    $nbRows = planningListFieldsForFilter();
  } else if($view!='MultipleUpadate'){
    $nbRows = listFieldsForFilter ( $obj, 0 );
  }else{
    $nbRows = listFieldsForMultipleUpdate ( $obj, 0 );
  }
  $json=ob_get_clean();
  $jsonValid='{"identifier":"id", "items":['.$json.']}';
  $arr=json_decode($jsonValid);
  if (!$arr) {
    errorLog("Cannot decode json string for fields list (jsonList.php - type='object')");
    errorLog($jsonValid);
    exit;
  }
  function build_sorter($key) {
    return function ($a, $b) use ($key) {
      return strnatcmp($a->$key, $b->$key);
    };
  }
  usort($arr->items, function ($a, $b) { return (strcasecmp(replace_accents($a->name),replace_accents($b->name))); });
  $result=pq_str_replace(array('[',']'),'',json_encode($arr->items));
  echo $result;
  //damian
}else if($type == "emailTemplate"){
  $objIdClass = RequestHandler::getValue('objectIdClass');
  $split=pq_explode('_',$objIdClass);
  $objectId = $split[0];
  $objectClass = $split[1];
  if($objectClass == 'TicketSimple'){
    $objectClass = 'Ticket';
  }
  $obj=new $objectClass($objectId);
  $emTp = new EmailTemplate();
  $idObjectType = SqlElement::getTypeName($objectClass);
  $idMailable = SqlList::getIdFromTranslatableName('Mailable', $objectClass);
  $where = "(idMailable = ".Sql::fmtId($idMailable)." or idMailable IS NULL)";
  if (property_exists($obj, $idObjectType)) $where .= " and (idType = ".Sql::fmtId($obj->$idObjectType)." or idType IS NULL)";
  $listEmailTemplate = $emTp->getSqlElementsFromCriteria(null,false,$where);
  $tabEmailTemplate = array();
  foreach ($listEmailTemplate as $val){
  	$tabEmailTemplate[$val->id]=$val->name;
  }
  foreach ($tabEmailTemplate as $id=>$name){
    echo '{id:"'.$id.'", name:"'.$name.'"},';
  }
} else if ($type == 'operator') { // =============================================== OPERATOR ===================================================================================
  $dataType = $_REQUEST ['dataType']; // Note: checked against constant values.
  if ($dataType == 'int' or $dataType == 'date' or $dataType == 'datetime' or $dataType == 'decimal') {
    echo ' {id:"=", name:"="}';
    echo ',{id:">=", name:">="}';
    if ($dataType == 'date' or $dataType == 'decimal') echo ',{id:">", name:">"}';
    echo ',{id:"<=", name:"<="}';
    if ($dataType == 'date' or $dataType == 'decimal') echo ',{id:"<", name:"<"}';
    echo ',{id:"<>", name:"<>"}';
    if ($dataType != 'int' and $dataType != 'decimal') {
      // echo ',{id:"xx", name:"xx"}';
      echo ',{id:"<=now+", name:"<= ' . i18n ( 'today' ) . ' + "}';
      echo ',{id:">=now+", name:">= ' . i18n ( 'today' ) . ' + "}';
      echo ',{id:"=month+", name:"' . i18n ( 'thisMonthPlus' ) . '"}';
      echo ',{id:"=year+", name:"'. i18n ( 'thisYearPlus' ) . '"}';
      echo ',{id:"isEmpty", name:"' . i18n ( 'isEmpty' ) . '"}';
      echo ',{id:"isNotEmpty", name:"' . i18n ( 'isNotEmpty' ) . '"}';   
    }
    echo ',{id:"SORT", name:"' . i18n ( 'sortFilter' ) . '"}';
  } else if ($dataType == 'varchar') {
    echo ' {id:"LIKE", name:"' . i18n ( "contains" ) . '"}';
    echo ',{id:"NOT LIKE", name:"' . i18n ( "notContains" ) . '"}';
    // ADD qCazelles - Dynamic filter - Ticket #78
    echo ',{id:"startBy", name:"' . i18n ( 'startBy' ) . '"}';
    echo ',{id:"isEmpty", name:"' . i18n ( 'isEmpty' ) . '"}';
    echo ',{id:"isNotEmpty", name:"' . i18n ( 'isNotEmpty' ) . '"}';
    echo ',{id:"SORT", name:"' . i18n ( 'sortFilter' ) . '"}';
  } else if ($dataType == 'bool') {
    echo ' {id:"=", name:"="}';
    echo ',{id:"SORT", name:"' . i18n ( 'sortFilter' ) . '"}';
  } else if ($dataType == 'list') {
    echo ' {id:"IN", name:"' . i18n ( "amongst" ) . '"}';
    echo ',{id:"NOT IN", name:"' . i18n ( "notAmongst" ) . '"}';
    echo ',{id:"isEmpty", name:"' . i18n ( 'isEmpty' ) . '"}';
    echo ',{id:"isNotEmpty", name:"' . i18n ( 'isNotEmpty' ) . '"}';
    echo ',{id:"SORT", name:"' . i18n ( 'sortFilter' ) . '"}';
  } else if ($dataType == 'hatchPattern') {
    echo ' {id:"=", name:"="}';
    echo ',{id:"<>", name:"' . i18n ( "differentFrom" ) . '"}';
    echo ',{id:"isEmpty", name:"' . i18n ( 'isEmpty' ) . '"}';
    echo ',{id:"isNotEmpty", name:"' . i18n ( 'isNotEmpty' ) . '"}';
  }else if ($dataType == 'refObject') {
    echo ' {id:"LIKE", name:"' . i18n ( "contains" ) . '"},';
    echo ' {id:"hasSome", name:"' . i18n ( "isNotEmpty" ) . '"}';
    // echo ',{id:"NOT LIKE", name:"' . i18n("notContains") . '"}';
  } else if($dataType =='indicatorFileNoteLink'){
    echo '{id:"isEmpty", name:"' . i18n ( 'isEmpty' ) . '"}';
    echo ',{id:"isNotEmpty", name:"' . i18n ( 'isNotEmpty' ) . '"}';
    echo ',{id:"hasNotes", name:"' . i18n ( 'hasNotes' ) . '"}';
    echo ',{id:"hasAttachments", name:"' . i18n ( 'hasAttachments' ) . '"}';
    echo ',{id:"hasLinks", name:"' . i18n ( 'hasLinks' ) . '"}';
  } else if ($dataType =='dependencies'){
    echo '{id:"isEmpty", name:"' . i18n ( 'isEmpty' ) . '"}';
    echo ',{id:"hasPredecessors", name:"' . i18n ( 'hasPredecessors' ) . '"}';
    echo ',{id:"hasSuccessors", name:"' . i18n ( 'hasSuccessors' ) . '"}';
  } else {
    echo ' {id:"UNK", name:"?"}';
    echo ',{id:"SORT", name:"' . i18n ( 'sortFilter' ) . '"}';
  }
} else if ($type == 'list') { // ================================================= LIST =======================================================================================
  $dataType = RequestHandler::getValue ( 'dataType' );
  $critField = RequestHandler::getValue ( 'critField' );
  $critValue = RequestHandler::getValue ( 'critValue' );
  $dataType=pq_str_replace(array('ActivityPlanningElement_','ProjectPlanningElement_','MilestonePlanningElement_','MeetingPlanningElement_','TestSessionPlanningElement_', 'PkerSessionPlanningElement_'),'',$dataType);
  if(pq_strpos($critValue, '_') != null){
  	$critValue = pq_explode('_', $critValue);
  }
  $selected = "";
  if (pq_strpos($dataType, "__id")>0) {
    $dataType=foreignKeyWithoutAlias($dataType);
  }
  if (pq_array_key_exists ( 'selected', $_REQUEST )) {
    $selected = $_REQUEST ['selected'];
  }
// MTY - LEAVE SYSTEM
  $leaveProjectId=null;
  if (isLeavesSystemActiv()) {
    if (pq_array_key_exists("withoutLeaveProject", $_REQUEST)) {
          if ($_REQUEST['withoutLeaveProject']==1) {
              $leaveProjectId = Project::getLeaveProjectId();
          }
    }
  }
// MTY - LEAVE SYSTEM    
  if ($dataType == 'planning') {
    $class = 'Project';
  } else if ($dataType == 'idStatusMandatoryNote') {
    $class = 'Status';
  } else {
    $class = pq_substr ( $dataType, 2 );
  }
  //Ticket 10325
//   if (Parameter::getGlobalParameter('requestorLimitToContact')!="YES"){ 
//     if ($dataType=='idContact' and $class=='Contact'){
//       $dataType='idAffectable';
//       $class='Affectable';
//     }
//   }
  if ($dataType == 'idStatusMandatoryNote' and $critField == 'idWorkflow') {
    $list=array();
    if ($critValue) {
      $workflow=new Workflow($critValue);
      $workflowStatuses=$workflow->getWorkflowStatusList();
      foreach ($workflowStatuses as $workflowStatus) {
        $list[$workflowStatus->id]=SqlList::getNameFromId('Status', $workflowStatus->id);
      }
      if ($selected and ! isset($list[$selected])) {
        $selected=null;
      }
    }
  } else if (($dataType == 'idContact' or $dataType == 'idAffectable') and $critField == 'idProject') {
    //$list = SqlList::getListWithCrit ( 'Contact', array($critField => $critValue) );
    if(is_array($critValue)){
      foreach ($critValue as $idProj){
        $prj=new Project($idProj, true);
        $lstTopSelectedPrj=$prj->getTopProjectList(true);
        foreach ($lstTopSelectedPrj as $idProject){
          $lstTopPrj[$idProject]=$idProject;
        }
      }
    }else{
      $prj=new Project($critValue, true);
      $lstTopPrj=$prj->getTopProjectList(true);
    }
    $in=transformValueListIntoInClause($lstTopPrj);
    $today=date('Y-m-d');
    $where="idProject in " . $in;
    $where.=" and idle=0";
    $where.=" and (endDate is null or endDate>='$today')";
    $aff=new Affectation();
    $listAff=$aff->getSqlElementsFromCriteria(null,null, $where);
    $nbRows=0;
    $list=array();
    if ($selected) {
      $selectList=pq_explode('_',$selected);
      foreach($selectList as $sel)
        $list[$sel]=SqlList::getNameFromId('Affectable', $sel);
    }
    foreach ($listAff as $aff) {
      if (! pq_array_key_exists($aff->idResource, $list)) {
        $id=$aff->idResource;
        $name=SqlList::getNameFromId(pq_substr($dataType, 2), $id);
        if ($name!=$id) {
          $list[$id]=$name;
        }
      }
    }
    asort($list);
  } else if ($dataType=='idComplexity' and $critField=='idWorkUnit' and $critValue) {
    $idWorkUnit = $critValue;
    $compValues = new ComplexityValues();
    $complexityValues = $compValues->getSqlElementsFromCriteria(array("idWorkUnit"=>$idWorkUnit));
    $list=array();
    foreach ($complexityValues as $value) {
      $nameComplexity = new Complexity($value->idComplexity);
      $list[$value->idComplexity]=$nameComplexity->name;
    }
  } else if ($dataType == 'idProject' and securityGetAccessRight ( 'menuProject', 'read' ) != 'ALL') {
    $user = getSessionUser ();
    $list = $user->getVisibleProjects ();
  }else if($dataType=='idBudgetParent'){
    $listBudgetElementary = SqlList::getList('BudgetItem','id',null,true);
    $showIdle = false;
    if($critValue =='on')$showIdle = true; 
    $budgetList=SqlList::getList('Budget','bbsSortable',$selected,$showIdle);
    $sepChar=Parameter::getUserParameter('projectIndentChar');
    if (!$sepChar) $sepChar='__';
    else if ($sepChar=='no') $sepChar='';
    $bbsLevelArray=array();
    $list = array();
    foreach($budgetList as $key => $val){
      if( in_array($key, $listBudgetElementary))continue;
      $budgetOrder = $budgetList[$key];
      $budgetTest=$budgetOrder;
      $level=1;
      while (pq_strlen($budgetTest)>4) {
        $budgetTest=pq_substr($budgetTest,0,pq_strlen($budgetTest)-6);
        if (pq_array_key_exists($budgetTest, $bbsLevelArray)) {
          $level=$bbsLevelArray[$budgetTest]+1;
          $budgetTest="";
        }
      }
      $bbsLevelArray[$budgetOrder]=$level;
      $sep='';
      for ($i=1; $i<$level;$i++) {
        if (pq_strpos($sepChar,'|')!==FALSE and $i<$level-1 and pq_strlen($sepChar)>1) {
          $sepCharW = str_repeat('..', 2);
        } else {$sepCharW = $sepChar;}
        $sep.=$sepCharW;
      }
      $val =$sep.SqlList::getNameFromId('Budget', $key);
      $list[$key]=$val;
      $selected=null;
   }
  }else if ($dataType == 'imputationResource') {
    $class = 'Affectable';
    $specific = 'imputation';
    $list = getListForSpecificRights ( $specific );
    $selectedProject = getSessionValue ( 'project' );
    if(pq_strpos($selectedProject, '_') != null){
      $selectedProject = pq_explode('_', $selectedProject);
    }
    $limitResourceByProj = Parameter::getUserParameter ( "limitResourceByProject" );
    if ($selectedProject and $selectedProject != '*' and $limitResourceByProj == 'on') {
      $restrictTableProjectSelected = array();
      $lstTopPrj=array();
      $sub=array();   
      if(! is_array($selectedProject)) $selectedProject=pq_explode(',',$selectedProject);
      foreach ($selectedProject as $idProj){
        $prj = new Project ( $idProj, true );
        $lstTopSelectedPrj = $prj->getTopProjectList ( true );
        foreach ($lstTopSelectedPrj as $idProject){
          $lstTopPrj[$idProject]=$idProject;
        }
        $subProj = $prj->getRecursiveSubProjectsFlatList ();
        foreach ($subProj as $id=>$name){
          $sub[$id]=$name;
        }
      }
      $in = transformValueListIntoInClause ( array_merge ( $lstTopPrj, array_keys ( $sub ) ) );
      $crit = 'idProject in ' . $in;
      $aff = new Affectation ();
      $lstAff = $aff->getSqlElementsFromCriteria ( null, false, $crit, null, true );
      foreach ( $lstAff as $id => $aff ) {
        $restrictTableProjectSelected [$aff->idResource] = $aff->idResource;
      }
    }
    $restrictArrayVisibility = getUserVisibleResourcesList ( true );
    foreach ( $list as $idR => $nameR ) {
      if (isset ( $restrictTableProjectSelected ) and ! isset ( $restrictTableProjectSelected [$idR] )) {
        unset ( $list [$idR] );
        continue;
      }
      if (! isset ( $restrictArrayVisibility [$idR] )) {
        unset ( $list [$idR] );
        continue;
      }
    }
    $user = getSessionUser ();
    if (! isset ( $list [$user->id] )) {
      $list [$user->id] = $user->name;
    }
  } else if ($dataType == 'planning') {
    $user = getSessionUser ();
    $list = $user->getVisibleProjects ();
    $restrictArray = $user->getListOfPlannableProjects ();
    //Flo #4311
    $administrativ=Project::getAdminitrativeProjectList(true);
    foreach ( $list as $prj => $prjname ) {
      if ($prj != '*' and ! isset ( $restrictArray [$prj] ) or pq_trim ( $prj ) == '' or isset($administrativ[$prj])) {
        unset ( $list [$prj] );
      }
// MTY - LEAVE SYSTEM
      if (isLeavesSystemActiv()) {
        if ($leaveProjectId!=null and $prj == $leaveProjectId) {
          unset ( $list [$prj] );              
    }
      }
// MTY - LEAVE SYSTEM
    }
  } else if ($dataType == 'idProfile' and pq_array_key_exists ( 'critField', $_REQUEST ) and pq_array_key_exists ( 'critValue', $_REQUEST ) and $_REQUEST ['critField'] == 'idProject') {
    $idProj = $_REQUEST ['critValue'];
    $user = new User ();
    $prf = new Profile ( getSessionUser ()->getProfile ( $idProj ) );
    $lstPrf = $prf->getSqlElementsFromCriteria ( null, false, "idle=0 and " . (($prf->sortOrder) ? 'sortOrder>=' . $prf->sortOrder : '1=1'), "sortOrder asc" );
    $list = array();
    foreach ( $lstPrf as $profile ) {
      $list [$profile->id] = i18n ( $profile->name );
    }
    if ($selected) {
      $aff = new Affectation ( $selected );
      $list [$aff->idProfile] = SqlList::getNameFromId ( 'Profile', $aff->idProfile );
      $selected = null;
    }
  } else if (($dataType == 'idProduct' or $dataType == 'idComponent' or $dataType == 'idProductOrComponent') and pq_array_key_exists ( 'critField', $_REQUEST ) and pq_array_key_exists ( 'critValue', $_REQUEST )) {
    if (pq_trim ( $_REQUEST ['critValue'] ) and $_REQUEST ['critField'] == 'idProject') {
      $list = array();
      $listProd = SqlList::getList ( $class );
      $versProj = new VersionProject ();
      $proj = new Project ( $_REQUEST ['critValue'],true );
      $lst = $proj->getTopProjectList ( true );
      $inClause = '(0';
      foreach ( $lst as $prj ) {
        if ($prj) {
          $inClause .= ',';
          $inClause .= $prj;
        }
      }
      $inClause .= ')';
      $versProjList = $versProj->getSqlElementsFromCriteria ( null, false, 'idProject in ' . $inClause );
      foreach ( $versProjList as $versProj ) {
        $vers = new Version ( $versProj->idVersion );
        if (isset ( $listProd [$vers->idProduct] )) {
          $list [$vers->idProduct] = $listProd [$vers->idProduct];
        }
      }
      // Add list of products directly linked to project (not only through version)
      $pp = new ProductProject ();
      $ppList = $pp->getSqlElementsFromCriteria ( null, false, 'idProject in ' . $inClause );
      foreach ( $ppList as $pp ) {
        if (isset ( $listProd [$pp->idProduct] ))
          $list [$pp->idProduct] = $listProd [$pp->idProduct];
      }
    } else if (pq_trim ( $_REQUEST ['critValue'] ) and $_REQUEST ['critField'] == 'idProduct') {
      $prod = new Product ( $_REQUEST ['critValue'] );
      $list = $prod->getComposition ( true, true );
      if ($dataType =='idComponent'){
        $componentTypeHide = SqlList::getListWithCrit('Type', array('lockUseOnlyForCC'=>'1','scope'=>'Component'));
        if (count($componentTypeHide)>0) foreach($list as $idT=>$valT) {
          $typeValue=SqlList::getFieldFromId('Component', $idT , 'idComponentType');
          if (isset($componentTypeHide[$typeValue]) ) {
            unset($list[$idT]);
          }
        }
      }
      if (trim($selected)) {
        $list [$selected] = SqlList::getNameFromId ( 'Component', $selected );
      }
    } else {
      $list = SqlList::getList ( $class );
    }
  } else if (pq_substr ( $dataType, 0, 2 ) == 'id' and pq_substr ( $dataType, - 4 ) == 'Type' and $dataType != 'idType' and $dataType != "idExpenseDetailType") {
    if ($class=='undefinedType') $list=array();
    else $list = SqlList::getList ( $class );
    if (pq_array_key_exists ( 'critField', $_REQUEST ) and pq_array_key_exists ( 'critValue', $_REQUEST )) {
      $critField = $_REQUEST ['critField'];
      $critVal = $_REQUEST ['critValue'];
      //if (pq_strpos($critVal,',')>0) $critVal=null; // Is it really usefull to have selection of multile projects...
      if ($critField == 'idProject') {
        if (pq_strpos($critVal, ',')) $critVal=pq_explode(',', $critVal);
        $rtListProjectType = Type::listRestritedTypesForClass ( $class, $critVal, null, null );
        if (count ( $rtListProjectType )) {
          $first=null;
          foreach ( $list as $id => $val ) {
            //if ($id != $selected and ! in_array ( $id, $rtListProjectType )) {
            if ( ! in_array ( $id, $rtListProjectType )) {
              unset ( $list [$id] );
            } else if (!$first) {
              $first=$id;
            }
          }
          if ($selected and  ! in_array ( $selected, $rtListProjectType )) {
            $selected=$first;
          }
        }
      }
      // $_REQUEST['required']='true';
    }
// PBER #10476
//   } else if ($dataType=='idBaselineSelect') { 
//     $list=array();
//     $critProj=(RequestHandler::getValue ('critField')=='idProject')?intval(RequestHandler::getValue('critValue')):null;
//     if ($critProj) {$critWhere='idProject = '.$critProj;}
//     else {$critWhere='idProject in '.getVisibleProjectsList(); }
//     $bl=new BaselineSelect;
//     $lstBaseline=$bl->getSqlElementsFromCriteria(null,null,$critWhere);
//     foreach ($lstBaseline as $bl) {
//       $list[$bl->id]=$bl->name." (".htmlFormatDate($bl->baselineDate).") - ".SqlList::getNameFromId('Project', $bl->idProject);
//     }
  }else if($dataType=="refTypeIncome" or $dataType=="refTypeExpense"){
    $list=array();
    $critArray=($dataType=="refTypeIncome")?array('type'=>'Income'):array('type'=>'Expense');
    $situationable= new Situationable();
    $listSituationable=$situationable->getSqlElementsFromCriteria($critArray);
    foreach ($listSituationable as $st){
      $list[$st->id]=i18n($st->name);
    }
  }else if (pq_array_key_exists ( 'critField', $_REQUEST ) and pq_array_key_exists ( 'critValue', $_REQUEST )) {
    $critField = $_REQUEST ['critField'];
    $critValue = $_REQUEST ['critValue'];
    if (($dataType == 'idVersion' or $dataType == 'idProductVersion' or $dataType == 'idComponentVersion' or $dataType == 'idOriginalVersion' or $dataType == 'idOriginalProductVersion' or $dataType == 'idOriginalComponentVersion' or $dataType == 'idTargetVersion' or $dataType == 'idTargetProductVersion' or $dataType == 'idTargetComponentVersion') and ($critField == 'idProductOrComponent' or $critField == 'idComponent')) {
      $critField = 'idProduct';
    }
    $showIdle = false;
    if ($critField == 'idle' and $_REQUEST ['critValue'] == 'all') {
      $showIdle = true;
      $crit = array();
    } else if ($critField=='idProject' and pq_substr($dataType, -16)=='ComponentVersion') {
      $crit = array('id'=>0);
    } else if (property_exists ( $class, $critField ) or ($critField == 'idProjectSub' and property_exists ( $class, 'idProject' )) or ($class == 'Indicator' and $critField == 'idIndicatorable') or (($class == 'WarningDelayUnit' or $class == 'AlertDelayUnit') and $critField == 'idIndicator')) {
      $crit = array($critField => $_REQUEST ['critValue']);
    } else if ($class== 'Command' &&  $critField=='idWorkCommand') {
      $Wc= new WorkCommand($critValue);
      $crit = array("id"=>$Wc->idCommand);
    } else {
      $crit = array();
    }
    if (isset ( $_REQUEST ['critField1'] ) and isset ( $_REQUEST ['critValue1'] )) {
      if ($_REQUEST ['critField1'] == 'idle' and $_REQUEST ['critValue1'] == 'all') {
        $showIdle = true;
      } else {
        $crit [$_REQUEST ['critField1']] = $_REQUEST ['critValue1'];
      }
    }
    $limitPlanning = Parameter::getGlobalParameter ( 'limitPlanningActivity' );
    if ($class == "Activity" and $limitPlanning == "YES") {
      $object = SqlElement::getCurrentObject ( null, null, true, false );
      if ($object and get_class ( $object ) == "Ticket") {
        $crit ['isPlanningActivity'] = 1;
      }
    }
    // ADD qCazelles
    if (($dataType=='idProductVersion' or $dataType=='idTargetProductVersion' or $dataType=='idOriginalProductVersion') and $critField=='idProject') {
    //if ($dataType == 'idProductVersion' and $critField == 'idProject') {
      // if (Parameter::getGlobalParameter('sortingLists')=='YES') {
      // $versionProject=new VersionProject();
      // $list=$versionProject->getVersionsFromProject($critValue);
      // } else {
      $proj = new Project ( $critValue,true );
      $listProjs = $proj->getRecursiveSubProjectsFlatList ( false, true );
      $clauseWhere = 'idProject in (0';
      foreach ( $listProjs as $idProj => $nameProj ) {
        if ($idProj) $clauseWhere .= ", $idProj";
      }
      $clauseWhere .= ')';
      $versionProject = new VersionProject ();
      $listVersionProjects = $versionProject->getSqlElementsFromCriteria ( null, false, $clauseWhere );
      $crit = array('id' => array());
      if (count ($listVersionProjects)==0 ) $crit ['id'] []=0;
      foreach ( $listVersionProjects as $versionProject ) {
        $crit ['id'] [] = $versionProject->idVersion;
      }
      $list = SqlList::getListWithCrit ( $class, $crit, 'name', null, $showIdle );
      // }
    } else {
      // END ADD qCazelles
      $list = SqlList::getListWithCrit ( $class, $crit, 'name', null, $showIdle );
      if ($dataType=='idDocumentVersion') {
        uasort($list, 'version_compare');
      }
      // Begin add gmartin /handle emailTemplates Ticket #157 - FIXED PBE
      if ($dataType=='idEmailTemplate' and isset ( $_REQUEST ['critField'] ) and isset ( $_REQUEST ['critValue'] ) ) {
        $list = array_merge_preserve_keys ( $list, SqlList::getListWithCrit ( $class, array($_REQUEST ['critField']=>null), 'name', null, false ) );
        if (isset ( $_REQUEST ['critField1'] ) and isset ( $_REQUEST ['critValue1'] ) ) {
          $list = array_merge_preserve_keys ( $list, SqlList::getListWithCrit ( $class, array($_REQUEST ['critField']=>$_REQUEST ['critValue'],$_REQUEST ['critField1']=>null), 'name', null, false ) );
        }
      }
      if ($dataType=='idBrand' && $critField=='idAssetType') {
        $brandsOfModels=SqlList::getListWithCrit('Model', array($critField=>$critValue),'idBrand');
        foreach($list as $id=>$val) {
          if (! in_array($id, $brandsOfModels) ) {
            unset($list[$id]);
          }
        }
      }
      if($class == 'Activity'){
        $object = SqlElement::getCurrentObject ( null, null, true, false );
        if($object and (get_class($object)=='Activity' or get_class($object)=='TestSession' or get_class($object)=='Milestone')) {
          $activityTypeList = "(".implode(',' ,SqlList::getListWithCrit('ActivityType', array('canHaveSubActivity'=>'1', 'idle'=>'0'),'id')).")";
          if ($activityTypeList=='()') $activityTypeList='(0)';
          $activity = new Activity();
          $critWhere = "idActivityType in $activityTypeList";
          if ($critField=='idProject' and $critValue=='*') { 
            // nothing 
          } else if ($critField and $critValue) {
            $critWhere .= " and $critField = $critValue";
          }
          $activityList = $activity->getSqlElementsFromCriteria(null,null,$critWhere,null,null, true);
          //if(count($activityList)>0)unset($table);
          $tableForType=array();
          foreach ($activityList as $id=>$act){
            $tableForType[$act->id]=$act->name;
          }
          $list=array_intersect_key($list, $tableForType);
        }
      }
      if ($class=='Activity' or $class=='Ticket') {
      	foreach ($list as $idL=>$valL) {
      		$list[$idL]=SqlList::formatValWithId($idL,$valL);
      	}
      }
      // end add gmartin - FIXED PBE
    }
  } else {
    $list = SqlList::getList ( $class );
    
    if($class == 'Status'){
      $workflowList = SqlList::getListWithCrit('Type', array('scope'=>$objectClass), 'idWorkflow');
      $workflowList = array_unique($workflowList);
      $where = (count($workflowList) > 0)?'idWorkflow in ('.implode(',', $workflowList).')':'1=1';
      $idStatusFrom = SqlList::getListWithCrit('WorkflowStatus', $where, 'idStatusFrom');
      $idStatusTo = SqlList::getListWithCrit('WorkflowStatus', $where, 'idStatusTo');
      $allStatus = array_unique(array_merge($idStatusFrom, $idStatusTo));
      $where = 'id in ('.implode(',', $allStatus).')';
      $list = SqlList::getListWithCrit($class, $where);
    }
    
    // ADD BY Marc TABARY - 2017-02-22 - RESOURCE VISIBILITY (list teamOrga)
    // Special case for idResource, idLocker, idResponsive
    // Don't see or access to the resource if is not visible for the user connected (respect of HabilitationOther - teamOrga)
    if ($class == 'Resource') {
      $listVisibleRes = getUserVisibleResourcesList ( true );
      $list = array_intersect_key ( $list, $listVisibleRes );
    }
    // ADD BY Marc TABARY - 2017-02-22 - RESOURCE VISIBILITY (list teamOrga)
// MTY - LEAVE SYSTEM
    if ($class == 'Project' and isLeavesSystemActiv()) {
        if (!Project::isProjectLeaveVisible()) {
            $idLeavePrj = Project::getLeaveProjectId();
            unset($list[$idLeavePrj]);
        }
    }
// MTY - LEAVE SYSTEM
    if ($class=='User'){
      uasort($list, function($a, $b) {
        return strcasecmp($a, $b);
      });
    }
  }
  if ($critField == 'scope' and $dataType = 'idEventForMail') {
    if (SqlElement::class_exists ( $critValue )) {
      // $objVal=new $critVal();
      if (! property_exists ( $critValue, 'idResource' )) {
        unset ( $list [1] ); // 1 responsibleChange
      }
      if (! property_exists ( $critValue, '_Note' )) {
        unset ( $list [2] ); // 2 noteAdd
        unset ( $list [4] ); // 4 noteChange
      }
      if (! property_exists ( $critValue, '_Link' )) {
        unset ( $list [12] ); // 12 linkAdd
        unset ( $list [13] ); // 13 linkDelete
      }
      if (! property_exists ( $critValue, '_Attachment' )) {
        unset ( $list [3] ); // 3 attachmentAdd
      }
      if ($critValue != 'Project') {
        unset ( $list [10] ); // 10 affectationAdd
        unset ( $list [11] ); // 11 affectationChange
      }
      if (! property_exists ( $critValue, '_Assignment' )) {
        unset ( $list [7] ); // 7 assignmentAdd
        unset ( $list [8] ); // 8 assignmentChange
      }
      if (! property_exists ( $critValue, 'description' )) {
        unset ( $list [5] ); // 5 descriptionChange
      }
      if (! property_exists ( $critValue, 'result' )) {
        unset ( $list [6] ); // 6 resultChange
      }
      if(! property_exists ( $critValue, 'idStatus' )){
        unset ( $list [14] ); // 14 status change
      }
      if(! property_exists ( $critValue, 'idPriority' )){
        unset ( $list [15] ); // 15 priorityChange
      }
      if($critValue!='User'){
        unset ( $list [16] );// 16 newUserCreated
      }
      /* 9 anyChange */
    }
  }
  /*
   * if ($dataType=='idResource') {
   * $scope=Affectable::getVisibilityScope();
   * if ($scope!="all") {
   * $list=array();
   * $res=new Resource();
   * if ($scope=='orga') {
   * $crit="idOrganization in (". Organization::getUserOrganisationList().")";
   * } else if ($scope=='orga') {
   * $crit="idOrganization in (". Organization::getUserOrganisationList().")";
   * } else if ($scope=='team') {
   * $aff=new Affectable(getSessionUser()->id,true);
   * $crit="idTeam='$aff->idTeam'";
   * } else {
   * traceLog("Error on htmlDrawOptionForReference() : Resource::getVisibilityScope returned something different from 'all', 'team', 'orga'");
   * $crit=array('id'=>'0');
   * }
   * $listRestrict=$res->getSqlElementsFromCriteria(null,false,$crit);
   * foreach ($listRestrict as $res) {
   * $list[$res->id]=$res->name;
   * }
   * asort($list);
   * }
   * $list = getUserVisibleResourcesList(true); // Try ?
   * }
   */
  if ($dataType=='idTargetProductVersion' or $dataType=='idProductVersion' or $dataType=='idOriginProductVersion') {
    $objectClass=RequestHandler::getValue('objectClass',false,null);
    if ($objectClass!='ProjectVersion') {
      // Must restrict to versions visible to user
      $restrictArray=getSessionUser()->getVisibleVersions();
      $list=array_intersect_key($list, $restrictArray);
    }
  }
  if ($dataType=='idProduct') {
    // Must restrict to products visible to user
    $restrictArray=getSessionUser()->getVisibleProducts();
    $list=array_intersect_key($list, $restrictArray);
  }

   if (pq_trim($selected)) {
    $selectList=pq_explode('_',$selected);
    foreach($selectList as $sel) {
      $name = SqlList::getNameFromId ( $class, $sel );
      if ($name == $sel and ($class == 'Resource' or $class == 'User' or $class == 'Contact')) {
        $name = SqlList::getNameFromId ( 'Affectable', $sel );
      }
      if ($name == $sel and pq_substr ( $class, - 7 ) == 'Version' and SqlElement::is_a ( $class, 'Version' )) {
        $name = SqlList::getNameFromId ( 'Version', $sel );
      }
      if ($class=='Activity' or $class=='Ticket') {
        $list [$sel] = SqlList::formatValWithId($sel,$name);
      } else {
        $list [$sel] = $name;
      }
    }
  }
  
  if ($dataType == "idProject" or $dataType == 'planning') {
    $wbsList = SqlList::getList ( 'Project', 'sortOrder', $selected, true );
  }
  $nbRows = 0;
  // return result in json format
  if (! pq_array_key_exists ( 'required', $_REQUEST ) and ! isset ( $_REQUEST ['critArray'] )) {
    if ($dataType == 'planning')
      echo '{id:" ", name:"' . i18n ( "allProjects" ) . '"}';
    else
      echo '{id:" ", name:""}';
    $nbRows += 1;
  }
  if ($dataType == "idProject" or $dataType == 'planning' or $dataType=="idSkill" or $dataType == "idOrganization") {
    $sepChar = Parameter::getUserParameter ( 'projectIndentChar' );
    if (! $sepChar) $sepChar = '__';
    else if ($sepChar=='no') $sepChar='';
    $wbsLevelArray = array();
  }
  if ($class=='Mailable' or $class=='Indicatorable' or $class=='Textable' or $class=='Checklistable' 
      or $class=='Linkable' or $class=='Copyable' or $class=='Dependable' or $class=='Originable'
      or $class=='Importable' or $class=='Notifiable' or $class=='Dependable' or $class=='Originable' or $class=='Situationable'){
    $temp=SqlList::getListNotTranslated($class,'name',$selected);
    foreach($temp as $key => $val){
      $checkMenu='menu'.$val;
      if ($val=='Assignment') $checkMenu='menuActivity';
      else if ($val=='TestCaseRun') $checkMenu='menuTestCase';
      else if ($val=='ProductStructure') $checkMenu='menuProduct';
      else if ($val=='Work') $checkMenu='menuImputation';
      else if ($val=='DocumentVersion') $checkMenu='menuDocument';
      if (! Module::isMenuActive($checkMenu)) unset($list[$key]);
      if ($class=='Linkable' or $class=='Copyable' or $class=='Dependable' or $class=='Originable') {
        $typeRight='read';
        if($class=='Copyable') $typeRight='create';
        $objTmp=new $val();
        if(securityGetAccessRightYesNo('menu'.$val, $typeRight, $objTmp)=="NO" or !securityCheckDisplayMenu(null,$val)) unset($list[$key]);
      }
    }
  }  
  if ($dataType == 'idLinkable' or $dataType == 'idCopyable' or $dataType == 'idImportable' or $dataType == 'idMailable' or $dataType == 'idIndicatorable' or $dataType == 'idChecklistable' or $dataType == 'idDependable' or $dataType == 'idOriginable' or $dataType == 'idReferencable' or $dataType == 'idNotifiable'  ) {
    asort ( $list );
  }
  if ($dataType=='idDocumentDirectory') {
    $list=SqlList::getList('DocumentDirectory','location');
    $idP=null;
    $obj=SqlElement::getCurrentObject();
    if ($critField=='idProject' and pq_trim($critValue)) $idP=$critValue;
    $prf=$user->getProfile($idP);
    $excludeArray=array();
    foreach ($list as $idT=>$valT) {
      $dr=SqlElement::getSingleSqlElementFromCriteria('DocumentRight',array('idDocumentDirectory'=>$idT,'idProfile'=>$prf),true);
      $am=new AccessProfile($dr->idAccessMode);
      $mode=($obj->id)?$am->idAccessScopeUpdate:$am->idAccessScopeCreate;
      //$mode=$am->idAccessScopeCreate;
      $right=SqlList::getFieldFromId('AccessScope', $mode, 'accessCode');
      if ($right=='NO') {
        $excludeArray[$idT]=$valT;
      } else if ($right=='PRO') {
        $affList=$user->getAffectedProjects(true);
        if (! isset($affList[$idP])) {
          $excludeArray[$idT]=$valT;
        }
      }
    }
    $list=array_diff ($list, $excludeArray);
  }
  if (Parameter::getGlobalParameter('allowListRestrictionOnProject')=='YES' and $critField=='idProject') {
    if (ListHideValue::isRestrictedList($class)) { 
      if ($critValue and ListHideValue::isRestrictedList($class,$critValue)) {
        $excludeArray=array();
        $hiddenValues=ListHideValue::getRestrictedValues($class, $critValue);
        foreach($hiddenValues as $hVal) {
          if (isset($list[$hVal])) $excludeArray[$hVal]=$list[$hVal];
        }
        $list=array_diff ($list, $excludeArray);
      }
    }
  }
  $pluginObjectClass = pq_substr ( $dataType, 2 );
  $table = $list;
  $lstPluginEvt = Plugin::getEventScripts ( 'list', $pluginObjectClass );
  foreach ( $lstPluginEvt as $script ) {
    require $script; // execute code
  }
  foreach ( $table as $id => $name ) {
    if (($dataType == "idProject" or $dataType == 'planning') and $sepChar != 'no' and $dataType!='idSkill') {
      
      if (isset ( $wbsList [$id] )) {
        $wbs = $wbsList [$id];
      } else {
        $wbsProj = new Project ( $id,true );
        $wbs = $wbsProj->sortOrder;
      }
      $wbsTest = $wbs;
      $level = 1;
      while ( pq_strlen ( $wbsTest ) > 3 ) {
        $wbsTest = pq_substr ( $wbsTest, 0, pq_strlen ( $wbsTest ) - 6 );
        if (pq_array_key_exists ( $wbsTest, $wbsLevelArray )) {
          $level = $wbsLevelArray [$wbsTest] + 1;
          $wbsTest = "";
        }
      }
      $wbsLevelArray [$wbs] = $level;
      $sep = '';
      for($i = 1; $i < $level; $i ++) {
        $sep .= $sepChar;
      }
      // $levelWidth = ($level-1) * 2;
      // $sep=($levelWidth==0)?'':pq_substr('_____________________________________________________',(-1)*($levelWidth));
      $name = $sep . $name;
    }else if($dataType=='idSkill' and $sepChar != 'no'){
      $skill= new Skill($id);
      $wbs=$skill->sbsSortable;
      $level=(pq_strlen($wbs)+1)/6;
      $sep = '';
      for ($i=1;$i<$level;$i++) {
        $sep .= $sepChar;
      }
      $name = $sep . $name;
    }else if ($dataType == "idOrganization") {
      $orgObj = new Organization ( $id, true );
      $wbs = $orgObj->sortOrder;
      $level = substr_count($wbs, '.') + 1;
      $wbsLevelArray [$wbs] = $level;
      $sep = '';
      for($i = 1; $i < $level; $i ++) {
        $sep .= $sepChar;
      }
      $name = $sep . $name;
    }
    if ($nbRows > 0)
      echo ', ';
    echo '{id:"' . htmlEncodeJson ( $id ) . '", name:"' . htmlEncodeJson ( $name ) . '"}';
    $nbRows += 1;
  }
} else if ($type == 'listResourceProject') { // ====================================================== LISTRESOURCEPROJECT ===================================================
  $idPrj = $_REQUEST ['idProject'];
  $arrayPrj=pq_explode(',',$idPrj);
  $lstTopPrj=array();
  foreach($arrayPrj as $idPrj) {
    $prj = new Project ( $idPrj,true );
    $lstTopPrj = array_merge($lstTopPrj,$prj->getTopProjectList ( true ));
  }
  $today = date ( 'Y-m-d' );
  $in = transformValueListIntoInClause ( $lstTopPrj );
  $where = "idle=0 and idProject in " . $in;
  // .$where.=" and (startDate is null or startDate<='$today')";
  $where .= " and (endDate is null or endDate>='$today')";
  if (isset ( $_REQUEST ['objectClass'] ) and $_REQUEST ['objectClass'] == 'IndividualExpense') {
    if (securityGetAccessRight ( 'menuIndividualExpense', 'read', null, getSessionUser () ) == 'OWN') {
      $where .= " and idResource=" . Sql::fmtId ( getSessionUser ()->id );
    }
  }
  $aff = new Affectation ();
  $list = $aff->getSqlElementsFromCriteria ( null, null, $where );
  $nbRows = 0;
  $lstRes = array();
  if (pq_array_key_exists ( 'selected', $_REQUEST )) {
    $lstRes [$_REQUEST ['selected']] = SqlList::getNameFromId ( 'Affectable', $_REQUEST ['selected'] );
  }
  // CHANGE BY Marc TABARY - 2017-02-21 - GENERIC FUNCTION IN PROJEQTOR.PHP
  $restrictArray = getUserVisibleResourcesList (true);
  // Old
  // $restrictArray=array();
  // END CHANGE BY Marc TABARY - 2017-02-21 - GENERIC FUNCTION IN PROJEQTOR.PHP
  // COMMENT BY Marc TABARY - 2017-02-21 - GENEREIC FUNCTION IN PROJEQTOR.PHP
  // $scope=Affectable::getVisibilityScope();
  // if ($scope!="all") {
  // $res=new Resource();
  // if ($scope=='orga') {
  // $crit="idOrganization in (". Organization::getUserOrganisationList().")";
  // } else if ($scope=='team') {
  // $aff=new Affectable(getSessionUser()->id,true);
  // $crit="idTeam='$aff->idTeam'";
  // } else {
  // traceLog("Error on htmlDrawOptionForReference() : Resource::getVisibilityScope returned something different from 'all', 'team', 'orga'");
  // $crit=array('id'=>'0');
  // }
  // $listRestrict=$res->getSqlElementsFromCriteria(null,false,$crit);
  // foreach ($listRestrict as $res) {
  // $restrictArray[$res->id]=$res->name;
  // }
  // }
  // END COMMENT BY Marc TABARY - 2017-02-21 - GENEREIC FUNCTION IN PROJEQTOR.PHP
  foreach ( $list as $aff ) {
    if (! pq_array_key_exists ( $aff->idResource, $lstRes )) {
      $id = $aff->idResource;
      $name = SqlList::getNameFromId ( 'Resource', $id );
      if ($name != $id) {
        // COMMENT BY Marc TABARY - 2017-03-07 - BUG Undefined variable: scope
        // Not needed because now
        // - $scope is retrieve in getUserVisibleResourceList
        // - $restrictArray is set by getUserVisibleResourceList
        // if ($scope=="all" or isset($restrictArray[$id])) {
        // $lstRes[$id]=$name;
        // }
        // END COMMENT BY Marc TABARY - 2017-03-07 - BUG Undefined variable: scope
        // ADD BY Marc TABARY - 2017-03-07 - BUG Undefined variable: scope
        // Apply realy the restriction
        if (pq_array_key_exists ( $aff->idResource, $restrictArray )) {
          $lstRes [$id] = $name;
        }
        // END ADD BY Marc TABARY - 2017-03-07 - BUG Undefined variable: scope
      }
    }
  }
  $pluginObjectClass = 'Affectable';
  $table = $lstRes;
  $lstPluginEvt = Plugin::getEventScripts ( 'list', $pluginObjectClass );
  foreach ( $lstPluginEvt as $script ) {
    require $script; // execute code
  }
  asort ( $table );
  // return result in json format
  if (! $required) {
    echo '{id:" ", name:""}';
    $nbRows += 1;
  }
  foreach ( $table as $id => $name ) {
    if ($nbRows > 0)
      echo ', ';
    echo '{id:"' . htmlEncodeJson ( $id ) . '", name:"' . htmlEncodeJson ( $name ) . '"}';
    $nbRows += 1;
  }
} else if ($type == 'listTermProject') {
  if (! isset ( $_REQUEST ['selected'] )) {
    $obj = SqlElement::getCurrentObject ( null, null, false, false ); // V5.2
    $idPrj = $_REQUEST ['idProject'];
    $prj = new Project ( $obj->idProject,true );
    $lstTopPrj = $prj->getTopProjectList ( true );
    $in = transformValueListIntoInClause ( $lstTopPrj );
    $where = "idProject in " . $in . " AND idBill is null";
    $term = new Term ();
    $list = $term->getSqlElementsFromCriteria ( null, null, $where );
    $listFinal = array();
    foreach ( $list as $term ) {
      // we get triggers
      $dep = new Dependency ();
      $crit = array("successorRefType" => "Term", "successorRefId" => $term->id);
      $depList = $dep->getSqlElementsFromCriteria ( $crit, false );
      $idle = 1;
      foreach ( $depList as $dep ) {
        switch ($dep->predecessorRefType) {
          case "Activity" :
            // $act = new Activity($dep->predecessorRefId);
            // if ($act->idle == 0) $idle = 0;
            break;
          case "Milestone" :
            $mil = new Milestone ( $dep->predecessorRefId );
            if ($mil->idle == 0)
              $idle = 0;
            break;
          case "Project" :
            // $project = new Project($dep->predecessorRefId);
            // if ($project->idle == 0) $idle = 0;
            break;
        }
      }
      // if all triggers are closed, so add term to list
      if ($idle == 1) {
        if ($term->date != null) {
          $now = date ( 'Y-m-d' );
          $now = new DateTime ( $now );
          $now = $now->format ( 'Y-m-d' );
          if ($now >= $term->date) {
            $listFinal [$term->id] = $term;
          }
        } else {
          $listFinal [$term->id] = $term;
        }
      }
    }
    foreach ( $listFinal as $term ) {
      if (! pq_array_key_exists ( $term->id, $listFinal )) {
        $listFinal [$term->id] = SqlList::getNameFromId ( 'Term', $term->id );
      }
    }
    
    asort ( $listFinal );
    // return result in json format
    echo '{id:null, name:""}';
    // $i=0;
    foreach ( $listFinal as $term ) {
      // if($i!=0)
      echo ', ';
      echo '{id:"' . $term->id . '", name:"' . $term->name . '"}';
      // $i++;
    }
  } else {
    echo '{id:"' . htmlEncodeJson ( $_REQUEST ['selected'] ) . '", name:"' . htmlEncodeJson ( SqlList::getNameFromId ( 'Term', $_REQUEST ['selected'] ) ) . '"}';
  }
} else if ($type == 'listRoleResource') {
  $ctrl = "";
  $idR = $_REQUEST ['idResource'];
  $resource = new ResourceAll( $idR );
  $nbRows = 0;
  if($resource->isResourceTeam){
    $role = new Role();
    $lstRoles = $role->getSqlElementsFromCriteria(array('idle'=>'0'));
    foreach ($lstRoles as $rol){
      if ($nbRows > 0)
        echo ', ';
      echo '{id:"' . $rol->id . '", name:"' . $rol->name . '"}';
      $nbRows += 1;
      $ctrl .= '#' . $rol->id . '#';
    }
  }else{
    if ($resource->idRole) {
      echo '{id:"' . $resource->idRole . '", name:"' . SqlList::getNameFromId ( 'Role', $resource->idRole ) . '"}';
      $nbRows += 1;
      $ctrl .= '#' . $resource->idRole . '#';
    }
    
    $where = "idResource=" . Sql::fmtId ( $idR ) . " and endDate is null";
    $where .= " and idRole <>" . Sql::fmtId ( $resource->idRole ) ;
    $rc = new ResourceCost ();
    $lstRoles = $rc->getSqlElementsFromCriteria ( null, false, $where );
    // return result in json format
    foreach ( $lstRoles as $resourceCost ) {
      $key = '#' . $resource->idRole . '#';
      //if (pq_strpos ( $ctrl, $key ) === false) {
        if ($nbRows > 0)
          echo ', ';
        echo '{id:"' . $resourceCost->idRole . '", name:"' . SqlList::getNameFromId ( 'Role', $resourceCost->idRole ) . '"}';
        $nbRows += 1;
        $ctrl .= $key;
      //}
    }
  }
}else if($type=="idWorkUnit"){
  $idWorkUnit = RequestHandler::getId('idWorkUnit');
  $complexityVal = new ComplexityValues();
  //$where = " (idWorkUnit = ".$idWorkUnit.") and  (price IS NOT NULL and charge IS NOT NULL) ";
  $where = " (idWorkUnit = ".$idWorkUnit.") ";
  $listComplexityValues = $complexityVal->getSqlElementsFromCriteria(null,false,$where);
  $tabComplexityValues = array();
  foreach ($listComplexityValues as $val){
    if(!$val->charge and !$val->duration and !$val->price)continue;
    $complexity = new Complexity($val->idComplexity);
    $tabComplexityValues[$complexity->id]=$complexity->name;
  }
   ksort($tabComplexityValues);
   echo '{id:"", name:""},';
  foreach ($tabComplexityValues as $id=>$name){
    echo '{id:"'.$id.'", name:"'.$name.'"},';
  }
}else if($type=="idWorkCommand"){
    $idWorkCommand = RequestHandler::getValue('idWorkCommand');
    $values = pq_explode("separator", $idWorkCommand);
    $idWorkUnit = $values[0];
    $idComplexity = $values[1];
    $idActivity = $values[2];
    $workUnit = new WorkUnit($idWorkUnit);
    $complexity = new Complexity($idComplexity);
    if($workUnit and $complexity and $idActivity){
//       if($idActivity){
        $act= new Activity($idActivity);
        $idProject =$act->idProject ;
//       }
      $catalog = new CatalogUO();
      $listCommand=SqlList::getListWithCrit('Command',array('idProject'=>$idProject),'id');
      $workCommand = new WorkCommand();
//       if($idActivity){
        //$act = new Activity($idActivity);
        if(property_exists($act, 'idClient')){
          if($act->idClient){
            $listCommand=SqlList::getListWithCrit('Command',array('idProject'=>$act->idProject,'idClient'=>$act->idClient),'id');
          }else{
            $listCommand=SqlList::getListWithCrit('Command',array('idProject'=>$act->idProject),'id');
          }
        }else{
          if($act->idContact){
            $contact = new Contact($act->idContact);
            $listCommand=SqlList::getListWithCrit('Command',array('idProject'=>$act->idProject,'idClient'=>$contact->idClient),'id');
          }else{
            $listCommand=SqlList::getListWithCrit('Command',array('idProject'=>$act->idProject),'id');
          }
        }
//       }
      $in=transformValueListIntoInClause($listCommand);
      $where = "( idCommand in ".$in.") and ( idWorkUnit = ".$idWorkUnit." and idComplexity = ".$idComplexity." ) ";
      $listWorkCOmmand = $workCommand->getSqlElementsFromCriteria(null,false,$where);
      $tabWorkCommand = array();
      foreach ($listWorkCOmmand as $val){
        $commandForRef = new Command($val->idCommand);
        if ($val->elementary == 1){
          $tabWorkCommand[$val->id]=($val->name!='')?'#'.$val->id.'-'.$commandForRef->reference.' - '.$val->name:$commandForRef->reference;
        }
        
      }
      ksort($tabWorkCommand);
      echo '{id:"", name:""},';
      foreach ($tabWorkCommand as $id=>$name){
        echo '{id:"'.$id.'", name:"'.$name.'"},';
      }
    }else{
      echo '{id:"", name:""},';
    }
} else if ($type == 'listStatusDocumentVersion') {
  $doc = SqlElement::getCurrentObject ( null, null, false, false ); // V5.2
  $idDocumentVersion = $_REQUEST ['idDocumentVersion'];
  $docVers = new documentVersion ( $idDocumentVersion );
  $table = SqlList::getList ( 'Status', 'name', $docVers->idStatus );
  if ($doc and $docVers->idStatus) {
    $profile = getSessionUser ()->getProfile ( $doc );
    $type = new DocumentType ( $doc->idDocumentType );
    $ws = new WorkflowStatus ();
    $crit = array('idWorkflow' => $type->idWorkflow, 'allowed' => 1, 'idProfile' => $profile, 'idStatusFrom' => $docVers->idStatus);
    $wsList = $ws->getSqlElementsFromCriteria ( $crit, false );
    $compTable = array($docVers->idStatus => 'ok');
    foreach ( $wsList as $ws ) {
      $compTable [$ws->idStatusTo] = "ok";
    }
    // Ticket #3417Ticket #3417
    $currentStatus=new Status($docVers->idStatus);
    if ($currentStatus->isCopyStatus) {
      $listAll=SqlList::getList('Status','id');
      $compTable[reset($listAll)]='ok';
    }
    $table = array_intersect_key ( $table, $compTable );
  } else {
    reset ( $table );
    $table = array(key ( $table ) => current ( $table ));
  }
  $nbRows = 0;
  foreach ( $table as $id => $name ) {
    if ($nbRows > 0)
      echo ', ';
    echo '{id:"' . $id . '", name:"' . $name . '"}';
    $nbRows += 1;
  }
}else if ($type=='listTagPerProject'){
  $idProject = RequestHandler::getId('idProject');
  $refType = RequestHandler::getClass('refType');
  $tag = new Tag();
  $listTag = $tag->getSqlElementsFromCriteria(array('idProject'=>$idProject,'refType'=>$refType));
  $nbRows = 0;
  $id = '';
  $name = '';
  foreach ($listTag as $t) {
    if ($nbRows > 0) echo ', ';
    else echo '{id:"' . $id . '", name:"' . $name . '"}, ';
    echo '{id:"'. $t->id .'", name :"' . $t->name. '"}';
    $nbRows += 1;
  }
}else if($type=="idWorkTokenMarkup"){
	$workTokenMarkup= new WorkTokenMarkup();
	$idWorkTokenCC=RequestHandler::getId('idWorkTokenCC');
	$workTokenCC=new WorkTokenClientContract($idWorkTokenCC);
	$lstWorkTokenMarkup=$workTokenMarkup->getSqlElementsFromCriteria(array("idWorkToken"=>$workTokenCC->idWorkToken));
	echo '{id:"", name:""},';
	foreach ($lstWorkTokenMarkup as $val){
	  echo '{id:"'.$val->id.'_'.$val->coefficient.'", name:"'.$val->name.'"},';
	}
} else if($type=="idWorkToken"){
    $idProj=RequestHandler::getId('idProject');
    $clientContract= new ClientContract();
    $workTokenCC= new WorkTokenClientContract();
    $tableCC=$clientContract->getDatabaseTableName();
    $queryLstCC="(SELECT DISTINCT tcc.id as id FROM $tableCC as tcc WHERE tcc.idProject=$idProj )";//and tcc.idle = 0
    $where=" idClientContract in $queryLstCC and fullyConsumed!=1 and idleToken=0";
    $lstTokenCC=$workTokenCC->getSqlElementsFromCriteria(null,false,$where);
	echo '{id:"", name:""},';
	foreach ($lstTokenCC as $val){
	  $tokenName=SqlList::getNameFromId('TokenDefinition', $val->idWorkToken);
	  $description=$val->description;
	  $pos=pq_strpos(nl2br($description), '<br />');
	  if($pos!==false){
	    $descriptionTrun=pq_substr($description,0,$pos);
	    $name=$tokenName.' - '.pq_substr($descriptionTrun,0, 30);
	  
	  }else{
	    $name=$tokenName.' - '.pq_substr($description,0, 30);
	  }
	  echo '{id:"'.$val->id.'", name:"'.$name.'"},';
	}
}
echo ' ] }';

function listFieldsForFilter($obj, $nbRows, $included = false) {
  // return result in json format
  global $contextForAttributes, $hideScope;
  $fieldType = RequestHandler::getValue('field');
  if($fieldType){
    if(pq_strpos($fieldType, 'Work'))$fieldType='Work';
    if(pq_strpos($fieldType, 'Cost') or pq_strpos($fieldType, 'Amount'))$fieldType='Cost';
    if(pq_strpos($fieldType, 'Date'))$fieldType='Date';
    if(pq_strpos($fieldType, 'pct') or pq_strpos($fieldType,'PlanningElement_progress') or pq_strpos($fieldType,'PlanningElement_expectedProgress') or pq_strpos($fieldType,'PlanningElement_unitProgress') or pq_strpos($fieldType,'rate'))$fieldType='Pct';
  }
  $contextForAttributes='global';
  $hideScope="column";
  if (method_exists($obj,'setAttributes')) $obj->setAttributes();
  foreach ( $obj as $col => $val ) {
    if (get_class($obj)=='GlobalView' and $col=='id') continue;
    if(pq_substr ( $col, 0, 1 ) != "_" and pq_substr ( $col, 0, 1 ) != pq_ucfirst ( pq_substr ( $col, 0, 1 ) )){
      if($fieldType=='Work' and !pq_strpos($col, 'Work'))continue;
      if($fieldType=='Cost' and (!pq_strpos($col, 'Cost') and !pq_strpos($col, 'Amount')))continue;
      if($fieldType=='Date' and !pq_strpos($col, 'Date'))continue;
      if($fieldType=='Pct'and (!pq_stripos($col, 'pct') and $col != 'unitProgress' and $col !='progress' and  $col != 'rate' ))continue;
    }
    if (!$fieldType and $col=='_Assignment') {
      if ($nbRows > 0) echo ', ';
      echo '{"id":"' . ($included ? get_class ( $obj ) . '_' : '') . 'assignedResource__idResourceAll' . '", "name":"' . i18n("assignedResource") . '", "dataType":"list"},';
      echo '{"id":"' . ($included ? get_class ( $obj ) . '_' : '') . 'assignedResourceLeftWork__idResourceAll' . '", "name":"' . i18n("assignedResourceLeftWork") . '", "dataType":"list"}';
      $nbRows+2;
      continue;
    }
    if (pq_substr ( $col, 0, 1 ) != "_" and pq_substr ( $col, 0, 1 ) != pq_ucfirst ( pq_substr ( $col, 0, 1 ) ) and ! $obj->isAttributeSetToField ( $col, 'hidden' ) and ! $obj->isAttributeSetToField ( $col, 'calculated' ) and 
    // ADD BY Marc TABARY - 2017-03-20 - FIELD NOT PRESENT FOR FILTER
    ! $obj->isAttributeSetToField ( $col, 'notInFilter' ) and 
    // END ADD BY Marc TABARY - 2017-03-20 - FIELD NOT PRESENT FOR FILTER
    (! $included or ($col != 'id' and $col != 'refType' and $col != 'refId' and $col != 'idle'))) {
      if ($nbRows > 0)
        echo ', ';
      $dataType = $obj->getDataType ( $col );
      $dataLength = $obj->getDataLength ( $col );
      if ($col == 'hatchPattern') $dataType = 'hatchPattern';
      if ($dataType == 'int' and $dataLength == 1) {
        $dataType = 'bool';
      } else if ($dataType == 'datetime') {
        $dataType = 'date';
      //} else if ((pq_substr ( $col, 0, 2 ) == 'id' and $dataType == 'int' and pq_strlen ( $col ) > 2 and pq_substr ( $col, 2, 1 ) == pq_strtoupper ( pq_substr ( $col, 2, 1 ) ))) {
      } else if (isForeignKey($col, $obj)) {
        $dataType = 'list';
      }
      $colName = $obj->getColCaption ( $col );
      if (pq_substr ( $col, 0, 9 ) == 'idContext') {
        $colName = SqlList::getNameFromId ( 'ContextType', pq_substr ( $col, 9 ) );
      }
      if (pq_substr($col,0,9)=='mandatory') { // add caption that appears after checkbox for fields with shorten name
        $found=0;
        $nextCaption=null;
        foreach ($obj->getFieldsList() as  $tmpcol) {
          if ($tmpcol==$col) {
            $found=1;
            continue;
          } else if ($found and pq_substr($tmpcol,0,5)=='_lib_') {
            $next=$tmpcol;
            $nextCaption=i18n(pq_substr($tmpcol, 5));
            break;
          }
        }
        if ($nextCaption) {
          $colName.=' ('.$nextCaption.')';
        }
      }
      $colName=json_encode(htmlspecialchars_decode($colName));
      echo '{"id":"' . ($included ? get_class ( $obj ) . '_' : '') . $col . '", "name":' . $colName . ', "dataType":"' . $dataType . '"}';
      if ($col == 'validatedEndDate') {
        echo ', {"id":"' . ($included ? get_class($obj) . '_' : '') . 'inheritedEndDate", "name":"' . i18n ( 'colInheritedEndDate' ) . '", "dataType":"' . $dataType . '"}';
      }
      $nbRows ++;
    } else if (pq_substr ( $col, 0, 1 ) != "_" and pq_substr ( $col, 0, 1 ) == pq_ucfirst ( pq_substr ( $col, 0, 1 ) )) {
      $sub = new $col ();
      $nbRows = listFieldsForFilter ( $sub, $nbRows, true );
    }
  }
  if (!$fieldType and isset ( $obj->_Note )) {
    if ($nbRows > 0)
      echo ', ';
    echo '{"id":"Note", "name":"' . i18n ( 'colNote' ) . '", "dataType":"refObject"}';
    $nbRows ++;
  }
  if (!$fieldType and get_class($obj)=='Assignment') {
    if ($nbRows > 0)
      echo ', ';
    echo '{"id":"itemName", "name":"' . i18n ( 'colItemName' ) . '", "dataType":"varchar"}';
    $nbRows ++;
  }
  if (!$fieldType and property_exists($obj, '_Note') || property_exists($obj, '_Attachment') || property_exists($obj, '_Link')) {
    if ($nbRows > 0)
      echo ', ';
    echo '{"id":"indicatorFileNoteLink", "name":"' . i18n ( 'colIndicatorFileNoteLink' ) . '", "dataType":"indicatorFileNoteLink"}';
    $nbRows ++;
  }
  $pe=get_class($obj).'PlanningElement';
  if (!$fieldType and property_exists($obj, $pe)) {
    if ($nbRows > 0)
      echo ', ';
    echo '{"id":"dependencies", "name":"' . lcfirst(i18n ( 'tabDependency' )) . '", "dataType":"dependencies"}';
    $nbRows ++;
  }
  return $nbRows;
}

function listFieldsForMultipleUpdate($obj, $nbRows,$pObj=false, $included = false) {
  global $contextForAttributes;
  $contextForAttributes="multipleUpdate";
  if (method_exists($obj,'setAttributes')) $obj->setAttributes();
  $extraHiddenFields = $obj->getExtraHiddenFields ( null, null, getSessionUser ()->getProfile () );
  $extraReadonlyFields = $obj->getExtraReadonlyFields ( null, null, getSessionUser ()->getProfile () );
  $proExist=property_exists(get_class($obj), SqlElement::getTypeName(get_class($obj)));
  //get my user
  $user=getSessionUser();
  //get my acces right for specificAccess param ( Can update creation information )
  $rightChangeSender = SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->idProfile, 'scope'=>'canUpdateCreation'));
  $rightChangeSender = $rightChangeSender->rightAccess;
  foreach ( $obj as $col => $val ) {
    //if my acces right are No don't display in list 
    if ($rightChangeSender=="2"){
      if($col=='idUser' or $col=='creationDate' or $col=='idleDate'){
        continue;
      }
    }
    if ($col=='_Assignment') {
      continue;
    }
    $colDisplay=true;
    if($proExist and ($col =='idle' or $col =='done' or $col=="handled" or $col=="cancelled" )){
      
      $type= new Type();
      $crit=array("scope"=>get_class($obj),"idle"=>"0");
      $critArray=array("scope"=>get_class($obj),"lock".pq_ucfirst($col)=>"1","idle"=>"0");
      $lstLockType=$type->countSqlElementsFromCriteria($critArray);
      $sumAllType=$type->countSqlElementsFromCriteria($crit);
      if($lstLockType==$sumAllType){
        $colDisplay=false;
      }
    }
    if($included and property_exists(get_class($pObj), $col) and ! $pObj->isAttributeSetToField ( $col, 'hidden' ) and ! $pObj->isAttributeSetToField ( $col, 'readonly' ) and ! $pObj->isAttributeSetToField ( $col, 'calculated' ))continue;
    if (pq_substr ( $col, 0, 9 ) == "_multiple" or $col=='uniqueResource' or $col=='proportional' or pq_substr ( $col, 0, 1 ) != "_" and pq_substr ( $col, 0, 1 ) != pq_ucfirst ( pq_substr ( $col, 0, 1 ) ) and ! $obj->isAttributeSetToField ( $col, 'hidden' ) and ! $obj->isAttributeSetToField ( $col, 'readonly' ) and $col!="originId"
     and ! $obj->isAttributeSetToField ( $col, 'calculated' )  and $col != 'id' and $col != '_Note' and $col != '_wbs' and $col !='wbs' and $col!='marginWorkPct' and $col!='marginCostPct' and $col!="password"
     and ! in_array($col,$extraHiddenFields) and ! in_array($col,$extraReadonlyFields) and $colDisplay){
      if ($nbRows > 0)echo ', ';
      $dataType = $obj->getDataType ( $col );
      $dataLength = $obj->getDataLength ( $col );
      $isMultipleInsert = (pq_substr ( $col, 0, 9 ) == "_multiple");
      if($isMultipleInsert){
        $dataType = 'multipleInsert';
        $dataLength = 0;
      }
//       if()
      if($col=="color")$dataType="color";
      if($col=="hatchPattern")$dataType="hatchPattern";
      
      if ($dataType == 'int' and $dataLength == 1) {
        $dataType = 'bool';
      }else if (isForeignKey($col, $obj)) {
        $dataType = 'list';
      }elseif ($dataType == 'varchar' and $dataLength >4000){
        $dataType = 'textarea';
      }elseif ($dataType == 'int' and $dataLength >1){
        $dataType = 'numeric';
      }
      $colName = $obj->getColCaption ( $col );
      if($isMultipleInsert){
        $colName = pq_str_replace("_multiple_", "", $col);
        $colName = i18n($colName);
      }
      if (pq_substr ( $col, 0, 9 ) == 'idContext') {
        $colName = SqlList::getNameFromId ( 'ContextType', pq_substr ( $col, 9 ) );
      }
      if (pq_substr($col,0,9)=='mandatory') { // add caption that appears after checkbox for fields with shorten name
        $found=0;
        $nextCaption=null;
        foreach ($obj->getFieldsList() as  $tmpcol) {
          if ($tmpcol==$col) {
            $found=1;
            continue;
          } else if ($found and pq_substr($tmpcol,0,5)=='_lib_') {
            $next=$tmpcol;
            $nextCaption=i18n(pq_substr($tmpcol, 5));
            break;
          }
        }
        if ($nextCaption) {
          $colName.=' ('.$nextCaption.')';
        }
      }
      $colName=json_encode(htmlspecialchars_decode($colName));
      if($isMultipleInsert){
        $col = pq_str_replace("_multiple_", "", $col);
      }
      echo '{"id":"' . ($included ? get_class ( $obj ) . '_' : '') . $col . '", "name":' . $colName . ', "dataType":"' . $dataType . '"}';
      $nbRows ++;
    } else if (pq_substr ( $col, 0, 1 ) != "_" and pq_substr ( $col, 0, 1 ) == pq_ucfirst ( pq_substr ( $col, 0, 1 ) ) ) {
      $sub = new $col ();
      $nbRows = listFieldsForMultipleUpdate ( $sub, $nbRows,$obj, true );
    }
  }
  if (isset ( $obj->_Note )) {
    if ($nbRows > 0)echo ', ';
    echo '{"id":"Note", "name":"' . i18n ( 'colNote' ) . '", "dataType":"note"}';
    $nbRows ++;
  }
  return $nbRows;
}
?>
