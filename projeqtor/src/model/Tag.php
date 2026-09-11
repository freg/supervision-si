<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2016 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 ******************************************************************************
 *** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
 ******************************************************************************
 * 
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module.
 * It is NOT distributed under an open source license. 
 * It is distributed in a proprietary mode, only to the customer who bought
 * corresponding licence. 
 * The company ProjeQtOr remains owner of all add-ons it delivers.
 * Any change to an add-ons without the explicit agreement of the company 
 * ProjeQtOr is prohibited.
 * The diffusion (or any kind if distribution) of an add-on is prohibited.
 * Violators will be prosecuted.
 *    
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ============================================================================
 * Activity is main planned element
 */  
require_once('_securityCheck.php');

class Tag extends SqlElement {

  public $id;
  public $name;
  public $refType;
  public $idle;
  public $idProject;
  
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
  
  public function control(){
    $result="";
    $user=getSessionUser();
    $canCreateTagsParam = SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->idProfile, 'scope'=>'canCreateTags'));
    $canCreateTags = ($canCreateTagsParam->id)?$canCreateTagsParam->rightAccess:2;
    if(!$this->id and $canCreateTags != 1){
      $result.='<br/>'.i18n('errorCreateRights').' '.i18n('colTags');
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }

  public static function saveTagList($newTags, $oldTags, $refType, $idProject=null) {
    $refType=self::getRefType($refType);
    $result='';
    $newTagList=pq_explode('#',pq_nvl($newTags));
    $oldTagList=pq_explode('#',pq_nvl($oldTags));
    $resultTagList = array();
    $tagPerProject=(Parameter::getGlobalParameter('listTagsPerProject')=="YES");
    foreach ($newTagList as $tag) {
      if (! pq_trim($tag)) continue;
      $crit=array('name'=>$tag, 'refType'=>$refType);
      if ($tagPerProject) $crit['idProject']=$idProject;
      $newTag=SqlElement::getSingleSqlElementFromCriteria('Tag',$crit);
      if (!$newTag->id) {
        $newTag->name=$tag;
        $newTag->idle=0;
        $newTag->refType=$refType;
        if($tagPerProject){
          $newTag->idProject=$idProject;
        }
        $resultTag = $newTag->save();
        if($resultTag != '' and getLastOperationStatus($resultTag) != 'OK'){
          $result = $resultTag;
          $resultTagList[]=$tag;
        }
      }
    }
    if ($refType) {
      $doc=new $refType();
      foreach ($oldTagList as $tag) {
        if (! pq_trim($tag)) continue;
        if (! in_array($tag, $newTagList)) { // Tag is deleted
          $cpt=$doc->countSqlElementsFromCriteria(null,"tags like '%#$tag#%'");
          if ($cpt==0) { // no more item uses this tag
            $crit=array('name'=>$tag, 'refType'=>$refType);
            if ($tagPerProject) $crit['idProject']=$idProject;
            $oldTag=SqlElement::getSingleSqlElementFromCriteria('Tag', $crit);
            if ($oldTag->id) {
              $oldTag->delete();
            }
          }
        }
      }
    }
    if($result != '' and getLastOperationStatus($result) != 'OK' and count($resultTagList) > 0){
      $result .= ' ('.implode(',', $resultTagList).')';
    }
    return $result;
  }
  
  public static function getRefType($class) {
    if ($class=='TicketSimple') return 'Ticket';
    if ($class=='PeriodicMeeting') return 'Meeting';
    return $class;
  }
}
?>