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
 * Client is the owner of a project.
 */  
require_once('_securityCheck.php'); 
class CatalogUOMain extends SqlElement {

  public $_sec_Description;
  public $id;
  public $name;
  public $nomemclature;
  public $idProject;
  public $numberComplexities;
  public $_spe_complexities;
  public $idle;
  public $_sec_unitOfWork;
  public $_spe_unitOfWork;
  public $_sec_phase;
  public $_spe_phase;
  public $_sec_Link;
  public $_Link = array();
  public $_Attachment = array();
  public $_Note = array();
  public $_nbColMax = 3;
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%"># ${id}</th>
    <th field="name" width="40%">${name}</th>
    <th field="nameProject" width="20%">${idProject}</th>
    <th field="nomemclature" width="30%">${nomemclature}</th>
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';
  
  private static $_colCaptionTransposition = array();
  
  private static $_fieldsAttributes=array(
      'name'=>'required',
      'idProject'=>'required'
  );
  
  private static $_databaseColumnName = array();
  
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

  public function save() {
    if(!$this->id){
      if(!$this->numberComplexities)$this->numberComplexities=Parameter::getGlobalParameter('ComplexitiesNumber');
    }
    //===== ticket #5987 : set catalog used on project when he hasn't catalog  ====//
    $old = $this->getOld();
    $saveProject=false;
    if((!$this->id and $this->idProject ) or ($this->id and $this->idProject != $old->idProject)){
      $proj=new Project($this->idProject);
      if(!$proj->idCatalogUO){
        $saveProject=true;
      }
    }
    //===== ticket #5987 : new Method, idProject in WorkUnit doesn't exist  ====//

//     else{
//       
//       if($this->idProject != $old->idProject){
//         $workU = new WorkUnit();
//         $lstWorkUnit = $workU->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
//         foreach ($lstWorkUnit as $woU){
//           $woU->idProject = $this->idProject;
//           $woU->save();
//         }
//       }
//     }
    $result=parent::save();
    if($saveProject){
      $proj->setRecursiveSubProjectCatalog($this->id,false,true);
    }
    return $result;
  }
  
  public function control(){
    $result="";
    $defaultControl=parent::control();
    $old = $this->getOld();
    
    //===== ticket #5987 : new Method, catalog can be used on many projects  ====//
  
//     $unicity = $this->countSqlElementsFromCriteria(array('idProject'=>$this->idProject));
//     if($unicity > 0){
//       if($this->id){
//         if($old->idProject != $this->idProject)$result .= '<br/>' . i18n ( 'projectIsAlreadyUsed' );
//       }else{
//         $result .= '<br/>' . i18n ( 'projectIsAlreadyUsed' );
//       }
//     }
    $nbComplex = Parameter::getGlobalParameter('ComplexitiesNumber'); 
    if($this->numberComplexities > $nbComplex and $nbComplex > 0){
      $result .= '<br/>' .  i18n('complexityCantBeSuperiorThan',array($nbComplex));;
     
    }
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function deleteControl() {
    $result="";
    $workUnit = new WorkUnit();
    $lstWOrkUnit = $workUnit->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
    foreach ($lstWOrkUnit as $wu){
      $actPl = new ActivityWorkUnit();
      $isUsed = $actPl->countSqlElementsFromCriteria(array('idWorkUnit'=>$wu->id));
      if ($isUsed){
        $result .= '<br/>' . i18n ( 'workUnitIsUseByActivity' );
      }
    }
    if ($result=="") {
      $result .= parent::deleteControl();
    }
    return $result;
  }
  
  public function copyTo($newClass, $newType, $newName, $newProject, $structure, $withNotes, $withAttachments, $withLinks, $withAssignments = false, $withAffectations = false, $toProject = NULL, $toActivity = NULL, $copyToWithResult = false, $copyToWithActivityPrice=false, $copyToWithStatus = false, $copyToWithSubTask=false, $moveAfterCreate=null) {
    $result=parent::copyTo($newClass,1, $newName, $newProject, false, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations, $toProject, $toActivity, $copyToWithResult, $copyToWithActivityPrice, $copyToWithStatus, false, $moveAfterCreate);
    $complexity = new Complexity();
    $listComplexity = $complexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
    foreach ($listComplexity as $comp){
      $complexitys = new Complexity();
      $complexitys->idCatalogUO = $result->id;
      $complexitys->name = $comp->name;
      $complexitys->idZone = $comp->idZone;
      $complexitys->save();
    }
    $workUnit = new WorkUnit();
    $listWorkUnit = $workUnit->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
    foreach ($listWorkUnit as $workU){
      $workUnits = new WorkUnit();
      $workUnits->idCatalogUO = $result->id;
//       $workUnits->idProject = $result->idProject;
      $workUnits->reference = $workU->reference;
      $workUnits->description = $workU->description;
      $workUnits->entering = $workU->entering;
      $workUnits->deliverable = $workU->deliverable;
      $workUnits->validityDate = $workU->validityDate;
      $workUnits->save();
      $valComplexity = new ComplexityValues();
      $listValComplexity = $valComplexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id,'idWorkUnit'=>$workU->id));
      foreach ($listValComplexity as $val){
        $valComplexitys = new ComplexityValues();
        $valComplexitys->idCatalogUO = $result->id;
        $myComplex = new Complexity($val->idComplexity);
        $complexityz=new Complexity();
        $complexityz=SqlElement::getSingleSqlElementFromCriteria("Complexity",array('name'=>$myComplex->name,'idZone'=>$myComplex->idZone,'idCatalogUO'=>$result->id));
        $valComplexitys->idComplexity = $complexityz->id;
        $valComplexitys->idWorkUnit = $workUnits->id;
        $valComplexitys->charge = $val->charge;
        $valComplexitys->price =$val->price;
        $valComplexitys->duration=$val->duration;
        $valComplexitys->save();
      }
    }
    return $result;
  }
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    if ($colName=="numberComplexities") {
      if($this->id){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  updateComplexities(dijit.byId("numberComplexities").get("value"),'.$this->id.','.Parameter::getGlobalParameter('ComplexitiesNumber').');';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
      }
    } 
    return $colScript;
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
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }
  
  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  /** =========================================================================
   * Draw a specific item for the current class.
   * @param String $item the item. Correct values are : 
   *    - subprojects => presents sub-projects as a tree
   * @return String an html string able to display a specific item
   *  must be redefined in the inherited class
   */
  public function drawSpecificItem($item){
    global $print;
    $result = "";
    if($item == "complexities"){
      if($this->id){
        echo'<tr>';
        echo ' <td><label></label></td><td>';
        echo '<div id="drawComplexity" dojotype="dijit.layout.ContentPane" widgetid="drawComplexity">';
        $nbComplexities = $this->numberComplexities;
        if(!$nbComplexities){
          $nbComplexities = Parameter::getGlobalParameter('ComplexitiesNumber');
        }
        $complexity = new Complexity();
        $list = $complexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
        drawComplexities($nbComplexities,$this,$list);
        echo '</div>';
        echo'</td></tr>';
      }
    }elseif($item== "unitOfWork"){
      if($this->id){
        $workUnit = new WorkUnit();
        $listWorkUnit = $workUnit->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
        $complexity = new Complexity();
        $listComplexity = $complexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
        drawWorkUnits($this,$listWorkUnit,$listComplexity);
      }
    }elseif($item== "phase"){
      if($this->id){
        $WorkUnitCatalogPhase = new WorkUnitCatalogPhase();
        $listWorkUnitCatalogPhase = $WorkUnitCatalogPhase->getSqlElementsFromCriteria(array('idCatalogUO'=>$this->id));
        drawWorkUnitCatalogPhase ($this,$listWorkUnitCatalogPhase,$this);
      }
    }
    return $result;
  }
  
  //===== function not used  ====//
  
//   public static function getProjectsUsingCatalog(){
//    $planningElement = new PlanningElement();
//    $plTable=$planningElement->getDatabaseTableName();
//     $querySelect = " SELECT DISTINCT  $plTable.idProject ";
//     $queryFrom = "   FROM $plTable ";
//     $queryWhere = "  WHERE $plTable.idWorkUnit IS NOT NULL ";
//     $query=$querySelect.$queryFrom.$queryWhere;
//     $result=Sql::query($query);
//     $tabIdProj = array();
//     while ($line = Sql::fetchLine($result)) {
//       $tabIdProj[]= $line['idProject'];
//     }
//     $crit = ' idWorkUnit IS NOT NULL ';
//     $tabIdProj = SqlList::getListWithCrit('PlanningElement', $crit , 'idProject');
//     return $tabIdProj;
//   }  
  
  //===== ticket #5987 : deprecated function ====//
//   public static function getCatalogueForProject($idProjet){
//     $proj = new Project($idProjet);
//     $topProj = $proj->getTopProjectList(true);
//     $projectCatalogUo = new CatalogUO();
//     $listProjCatalog = SqlList::getList('CatalogUO','idProject');
//     $result = null;
//     foreach ($topProj as $idProj){
//       if($result)break;
//       if(in_array($idProj, $listProjCatalog))$result=$idProj;
//     }
//     return $result;
//   }
  
  public static function isCatalogUsedOnProject($idProject, $idCatalog){
    if (! $idCatalog or ! is_numeric($idCatalog)) return false;
    if (! $idProject or ! is_numeric($idProject)) return false;
    $wu=new WorkUnit();$wuTable=$wu->getDatabaseTableName();
    $awu=new ActivityWorkUnit();$awuTable=$awu->getDatabaseTableName();
    $pe=new PlanningElement();$peTable=$pe->getDatabaseTableName();
    $countQuery="SELECT count(*) as cpt FROM $wuTable wu, $awuTable awu, $peTable as pe "
               ."WHERE wu.idCatalogUO=$idCatalog and wu.id=awu.idWorkUnit and pe.refType=awu.refType and pe.refId=awu.refId and pe.idProject=$idProject";
    $result = Sql::query($countQuery); 
    $line = Sql::fetchLine($result);
    if (!$line or !$line['cpt']) {
      return false;
    } else if ($line['cpt']>0) {
      return true;
    } else {
      return false;
    }
  }
}
?>