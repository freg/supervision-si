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

/** ============================================================================
 * Action is establised during meeting, to define an action to be followed.
 */ 
require_once('_securityCheck.php');

class SkillMain extends SqlElement {

  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id;
  public $name;
  public $idSkill;
  public $sbs;
  public $sbsSortable;
  public $_spe_showStructure;
  public $idle;
  public $description;
  public $_nbColMax=3;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%" ># ${id}</th>
    <th field="sbsSortable" formatter="sortableFormatter" width="5%" >${sbs}</th>
    <th field="name" width="20%" >${name}</th>
    <th field="idle" width="4%" formatter="booleanFormatter" >${idle}</th>
    ';
  
  private static $_fieldsAttributes=array(
      "name"=>"required,unique",
      "sbs"=>"display,noImport",
      "sbsSortable"=>"hidden,noImport"
  );  
  
  private static $_colCaptionTransposition = array(
      'idSkill'=>'parentSkill'
  );
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if ($withoutDependentObjects) return;
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
  
// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    return $colScript;
  }
  
//   public function save() {
//   }
  
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
  	if($item == 'showStructure'){
  		if ($print or !$this->id) return "";
  		$result='<table>';
  		$result.='<tr>';
  		$result.='<td rowspan="2" style="padding-left:183px">';
  		$result.='<button id="showSkillStructure" dojoType="dijit.form.Button" showlabel="true"';
  		$result.=' class="roundedVisibleButton" title="'.i18n('showStructure').'" style="vertical-align: middle;">';
  		$result.='<span>' . i18n('showStructure') . '</span>';
  		$result.='<script type="dojo/connect" event="onClick" args="evt">';
  		$page="../view/skillStructure.php?id=$this->id";
  		$result.="var url='$page';";
  		$result.='showPrint(url, "skill", null, "html", "P");';
  		$result.='</script>';
  		$result.='</button>';
  		$result.='</div></td>';
  		$result.='</tr></table>';
  	}
  	return $result;
  }
  
  public function getRecursiveSubSkill($includeSelf=false){
  	$crit=array('idSkill'=>$this->id);
  	$obj=new Skill($this->id);
  	$subSkills=$obj->getSqlElementsFromCriteria($crit, false,null,null,null,true) ;
  	$subSkillList=array();
  	$parentSubSkillList=array();
  	foreach ($subSkills as $subSkill) {
  		$recursiveList=null;
  		$recursiveList=$subSkill->getRecursiveSubSkill();
  		$arraySkill=array('id'=>$subSkill->id, 'name'=>$subSkill->name, 'subItems'=>$recursiveList);
  		$subSkillList[]=$arraySkill;
  	}
  	if($includeSelf){
  	  $parentSubSkillList[]=array('id'=>$obj->id, 'name'=>$obj->name, 'subItems'=>$subSkillList);
  	  return $parentSubSkillList;
  	}else{
  	  return $subSkillList;
  	}
  }
  
  public function getRecursiveFlatSubSkill($includeSelf=false, $showIdle=false) {
  	if (!$this->id) return array();
  	$sub=SqlList::getListWithCrit('Skill',array('idSkill'=>$this->id),'id',null,$showIdle);
  	foreach ($sub as $sklId) {
  		$skl=new Skill($sklId,true);
  		$subList=$skl->getRecursiveFlatSubSkill();
  		$sub=array_merge_preserve_keys($sub,$subList);
  	}
  	if($includeSelf)$sub[$this->id]=$this->id;
  	return $sub;
  }
  
  public function getParentSkill() {
  	$result=array();
  	if ($this->idSkill) {
  		$parent=new Skill($this->idSkill);
  		$result=array_merge_preserve_keys($parent->getParentSkill(),array($parent->id=>$parent->name));
  	}
  	return $result;
  }
  
  public function getTopParentSkill() {
  	$result=$this->id;
  	if ($this->idSkill) {
  		$parent=new Skill($this->idSkill);
  		$result=($parent->idSkill)?$parent->getTopParentSkill():$parent->id;
  	}
  	return $result;
  }
  
  public function getTopParentSkillList() {
  	if (! $this->idSkill) {
  		return array();
  	} else {
  		$parent=new Skill($this->idSkill);
  		$topList=$parent->getTopParentSkillList();
  		$result=array_merge(array($this->idSkill),$topList);
  		return $result;
  	}
  }
  
  public function isElementary(){
  	$result = true;
  	$cpt = $this->countSqlElementsFromCriteria(array('idSkill'=>$this->id));
  	if($cpt > 0)$result = false;
  	return $result;
  }
  
  public function save() {
  	$old=$this->getOld();
  	$result="";
	$result = parent::save();
  	// UPDATE PARENTS (recursively)
  	if ($this->idSkill) {
  		$parent=new Skill($this->idSkill);
  		$parent->save();
  	}
  	if ($old->idSkill and $old->idSkill!=$this->idSkill) {
  		$parent=new Skill($old->idSkill);
  		$parent->save();
  	}
  	if (!$this->sbs or !$old->id or $old->idSkill!=$this->idSkill) {
  		$parent=new Skill($this->idSkill);
  		$parent->regenerateSbsLevel();
  		if ($old->id and $this->idSkill!=$old->idSkill) {
  			$parent=new Skill($old->idSkill);
  			$parent->regenerateSbsLevel();
  		}
  	}
  	return $result;
  }
  
  public function control(){
  	$result="";
  	$old=$this->getOld();
  	if ($this->id and $this->id==$this->idSkill) {
  		$result.='<br/>' . i18n('errorHierarchicLoop');
  	}
  	$defaultControl=parent::control();
  	if ($defaultControl!='OK') {
  		$result.=$defaultControl;
  	}
  	if ($result=="") {
  		$result='OK';
  	}
  	return $result;
  }
  
  public function simpleSave($withoutDependencies=false) {
  	return parent::save();
  }
  public function delete() {
  	$result = parent::delete();
  	if ($this->idSkill) {
  		$parent=new Skill($this->idSkill);
  		$parent->save();
  		$parent->regenerateSbsLevel();
  	}
  	return $result;
  }
  
  public function regenerateSbsLevel() {
  	$sbs=$this->sbs;
  	if ($sbs) $sbs.='.';
  	else $sbs='';
  	$items=$this->getSqlElementsFromCriteria(array('idSkill'=>$this->id),null,null,"coalesce(sbsSortable,'99999') asc");
  	$cpt=0;
  	foreach($items as $item) {
  		$cpt++;
  		if ($sbs.$cpt!=$item->sbs) {
  			$item->sbs=$sbs.$cpt;
  			$item->sbsSortable=formatSortableWbs($item->sbs);
  			$item->simpleSave();
  			$item->regenerateSbsLevel();
  		}
  	}
  
  }
  
  public function moveTo($destId,$mode,$recursive=false) {
  	$status="WARNING";
  	$result="";
  	$returnValue="";
  	$skl=null;
  	$dest=new Skill($destId);
  	$changeparent=false;
  	if ($dest->idSkill!=$this->idSkill) {    // Change parent
  		$changeparent=true;
  		$this->idSkill=$dest->idSkill;   // Move under same Skill
  		$status="OK";
  		if (!$this->idle and $dest->idle) { // Move non idle after/before idle : check if new parent is idle
  			$destParent=new Skill($dest->idSkill);
  			if ($destParent->idle) { // Move non closed item under closed item : forbidden
  				$returnValue=i18n('moveCancelledIdle');
  				$status="WARNING";
  			}
  		}
  	} else { // Don't change parent => just reorder at same level
  		$status="OK";
  	}
  
  	$parent=new Skill($dest->idSkill);
  	if ($status=="OK" and $changeparent and  !$recursive) { // Change parent, then will recursively call moveTo to reorder correctly
  		$oldParentId=$this->idSkill;
  		$resultSkill=$this->save();
  		if (pq_stripos($resultSkill,'id="lastOperationStatus" value="OK"')>0 ) {
  			$skill=new Skill($this->id);
  			$skill->moveTo($destId,$mode,true);
  			$returnValue=i18n('moveDone');
  		} else {
  			$returnValue=$resultSkill;//i18n('moveCancelled');
  			$status=getLastOperationStatus($resultSkill);
  		}
  	} else if ($status=="OK") { // Just reorder on same level
  		$where=($this->idSkill)? $where="idSkill=".Sql::fmtId($this->idSkill): "idSkill is null";
  		$order="sbsSortable asc";
  		$list=$this->getSqlElementsFromCriteria(null,false,$where,$order);
  		$idx=0;
  		$currentIdx=0;
  
  		foreach ($list as $skl) {
  			if ($skl->id==$this->id) continue;
  			if ($skl->id==$destId and $mode=="before") {
  				$idx++;
  				$currentIdx=$idx;
  			}
  			$idx++;
  			$root=pq_substr($skl->sbs,0,strrpos($skl->sbs,'.'));
  			$oldBbs=$skl->sbs;
  			$skl->sbs=($root=='')?$idx:$root.'.'.$idx;
  			if ($oldBbs!=$skl->sbs) {
  				$skl->sbsSortable=formatSortableWbs($skl->sbs);
  				$skl->simpleSave();
  				$skl->regenerateBbsLevel();
  			}
  			if ($skl->id==$destId and $mode=="after") {
  				$idx++;
  				$currentIdx=$idx;
  			}
  		}
  
  		$root=pq_substr($this->sbs,0,strrpos($this->sbs,'.'));
  		$this->sbs=($root=='')?$currentIdx:$root.'.'.$currentIdx;
  		$this->sbsSortable=formatSortableWbs($this->sbs);
  		$this->simpleSave();
  		$returnValue=i18n('moveDone');
  		$status="OK";
  	}
  
  	$returnValue .= '<input type="hidden" id="lastOperation" value="move" />';
  	$returnValue .= '<input type="hidden" id="lastOperationStatus" value="' . $status . '" />';
  	$returnValue .= '<input type="hidden" id="lastPlanStatus" value="OK" />'; // Must send OK to refresh planning (and revert move)
  	return $returnValue;
  }
  
  public static function getSubSkillList($subList, &$subSkill){
    foreach ($subList as $id=>$obj){
      $subSkill[]=$obj->id;
      $skill = new Skill();
      $resubList = $skill->getSqlElementsFromCriteria(array('idSkill'=>$obj->id));
      $skill->getSubSkillList($resubList, $subSkill);
    }
  }
}
?>