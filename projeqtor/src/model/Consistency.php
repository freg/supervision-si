<?php 
use Doctrine\Common\Persistence\Mapping\AbstractClassMetadataFactory;

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
 * Technical class to implement consistency checks
 */ 
require_once('_securityCheck.php');

class Consistency {

   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {

  }

   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    
  }
  
  // =================================================================================================================
  // WBS Ordering
  // =================================================================================================================
  
  /**
   * Check consistency of WBS ordering
   * @param string $if($print)display
   * @param string $correct
   */
  
//   public static function checkWbs($correct=false,$trace=false,$print=true) {
//     debugTraceLog("checkWbs - correct WBS index in Projects Structure");
//     $pe=new PlanningElement();
//     $peList=$pe->getSqlElementsFromCriteria(null,null,"1=1",'wbsSortable asc');
//     $lastWbs='';
//     $lastPe=$pe;
//     $errors=0;
//     $arrayWbs=array();
//     foreach ($peList as $idx=>$pe) {
//       $currentWbs=$pe->wbsSortable;
//       if ($trace) echo "$pe->wbsSortable - $pe->refType #$pe->refId - $pe->refName<br/>";
//       if (!$pe->refType or !$pe->refId) {
//         if($print)displayError(i18n("checkPlanningElementEmpty",array(i18n($pe->refType),$pe->refId,$pe->id)));
//         $errors++;
//         if ($correct) {
//           $resultDeletePE=$pe->delete();
//           if (getLastOperationStatus($resultDeletePE=="OK")) {
//             if($print)displayOK(i18n("checkFixed"),true);
//           } else {
//             if($print)displayMsg(i18n("checkNotFixed"),true);
//           }
//         }
//         continue;
//       }
//       // check for duplicate WBS
//       if ($pe->wbsSortable==$lastWbs) {
//         if($print)displayError(i18n("checkWbsDuplicate",array($lastWbs,i18n($lastPe->refType),$lastPe->refId,i18n($pe->refType),$pe->refId)));
//         $errors++;
//         if ($correct) {
//           self::fixOrder($pe,"duplicate",$peList,$idx,get_class($pe),$print);
//         }
//       }
//       // Check Parent
//       $parentWbs='';
//       if ($pe->topRefType and $pe->topRefId) {
//         $key=$pe->topRefType.'#'.$pe->topRefId;
//         $parentWbs=(isset($arrayWbs[$key]))?$arrayWbs[$key]:'';
//         if (!$parentWbs) { // Possibly just incorrect order
//           $parentPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$pe->topRefType, 'refId'=>$pe->topRefId));
//           if ($parentPe and $parentPe->id) {
//             $parentWbs=$parentPe->wbsSortable;
//           }
//         }
//         if ($parentWbs=='') {
//           if($print)displayError(i18n("checkWbsParentNotFound",array($pe->topRefType,$pe->topRefId, i18n($pe->refType), $pe->refId)));
//           $errors++;
//           if ($correct) {
//             if($print)displayError(i18n("checkCannotFix"),true);
//           }
//         }
//       }
//       if ($parentWbs and $parentWbs!=pq_substr($pe->wbsSortable,0,pq_strlen($parentWbs))) {
//         if($print)displayError(i18n("checkWbsParentIssue",array($pe->wbsSortable,i18n($pe->refType),$pe->refId,$parentWbs,$pe->topRefType,$pe->topRefId)));
//         $errors++;
//         if ($correct) {
//           self::fixOrder($pe,"parent",$peList,$idx,get_class($pe),$print);
//         }
//       } else if ($parentWbs and pq_strlen($pe->wbsSortable)!=pq_strlen($parentWbs)+6) {
//         if($print)displayError(i18n("checkWbsParentIssue",array($pe->wbsSortable,i18n($pe->refType),$pe->refId,$parentWbs,$pe->topRefType,$pe->topRefId)));
//         $errors++;
//         if ($correct) {
//           self::fixOrder($pe,"parent",$peList,$idx,get_class($pe),$print);
//         }
//       }
//       // Check Order
//       $order=pq_substr($pe->wbsSortable,-5);
//       if ($lastWbs==$parentWbs) { // Previous is parent, so must be 001
//         if (intval($order)!=1 and ($pe->wbsSortable!='00000' or $pe->refType!='Project')) {
//           if($print)displayError(i18n("checkWbsFirst", array($pe->wbsSortable,i18n($pe->refType),$pe->refId)));
//           $errors++;
//           if ($correct) {
//             self::fixOrder($pe,"first",$peList,$idx,get_class($pe),$print);
//           }
//         }
//       } else if (pq_substr($lastWbs,0,-6)==$parentWbs) { // Previous has same root (same parent), number must be is sequence
//         if (intval($order)!=intval(pq_substr($lastWbs,-5))+1) {
//           if($print)displayError(i18n("checkWbsOrder",array($pe->wbsSortable, i18n($pe->refType), $pe->refId, $lastWbs)));
//           $errors++;
//           if ($correct) {
//             self::fixOrder($pe,"order",$peList,$idx,get_class($pe),$print);
//           }
//         }
//       } else { // Change root, current numbering must be is sequence
//         $rootPrev=pq_substr($lastWbs,0,pq_strlen($pe->wbsSortable));
//         if (intval($order)!=intval(pq_substr($rootPrev,-5))+1) {
//           if($print)displayError(i18n("checkWbsOrder",array($pe->wbsSortable, i18n($pe->refType), $pe->refId,$lastWbs)));
//           $errors++;
//           if ($correct) {
//             self::fixOrder($pe,"order",$peList,$idx,get_class($pe),$print);
//           }
//         }
//       }
//       // Check if($print)displayed wbs compared to wbsSortable
  
//       // Check project order
//       if ($pe->refType=='Project') {
//         $prj=new Project($pe->refId);
//         $pe=$prj->ProjectPlanningElement;
//         if ($prj->sortOrder!=$pe->wbsSortable) {
//           if($print)displayError(i18n("checkWbsSortOrderProject",array($prj->id,$prj->sortOrder,$pe->wbsSortable)));
//           $errors++;
//           if ($correct) {
//             $prj->sortOrder=$pe->wbsSortable;
//             $res=$prj->save();
//             if (getLastOperationStatus($res)=='OK'  or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
//             else if($print)displayError($res,true);
//           }
//         }
  
//       }
//       // Continue
//       $key=$pe->refType.'#'.$pe->refId;
//       $arrayWbs[$key]=$currentWbs;
//       $lastWbs=$currentWbs;
//       $lastPe=$pe;
//     }
//     if (!$errors) {
//       if($print)displayOK(i18n("checkNoError"));
//     }
//   }
  
  public static function checkWbs($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkWbs - correct WBS index in Projects Structure");
    $pe=new PlanningElement(); $peTable=$pe->getDatabaseTableName();
    $p=new Project(); $pTable=$p->getDatabaseTableName();
    $errors=0;
    // First check correc t project in PlanningElement
    $peListQuery="SELECT p.id as id, p.idProject as idproject, pe.topRefId as toprefid, pe.id as idpe "
                ."FROM $pTable p inner join $peTable pe on pe.refType='Project' and p.id=pe.refId "
                ."WHERE p.idProject!=pe.topRefId";
    $resultProjects=Sql::query($peListQuery);
    while ($line = Sql::fetchLine($resultProjects)) {
      $id=$line['id'];
      $idproject=$line['idproject'];
      $toprefid=$line['toprefid'];
      $idpe=$line['idpe'];
      $pe=new PlanningElement($idpe);
      $topPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>'Project', 'refId'=>$idproject) );
      if($print)displayError(i18n("checkWbsParentIssue",array($pe->wbs,'Project', $id, $topPe->wbs, 'Project', $idproject)));
      $errors++;
      if ($correct) {  
        $pe->topRefId=$idproject;
        $pe->topId=$topPe->id;
        $pe->wbs=null;
        $pe->wbsSortable=null;
        $resultUpdatePE=$pe->save();
        if (getLastOperationStatus($resultUpdatePE=="OK")) {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    
    
    //$peList=$pe->getSqlElementsFromCriteria(null,null,"1=1",'wbsSortable asc');
    $peListQuery="select id, refType as reftype, refId as refid, wbsSortable as wbs, refName as name, topRefType as topreftype, topRefId as toprefid, topId as topid from $peTable order by wbsSortable asc";
    $result=Sql::query($peListQuery);
    $lastWbs='';
    $lastRefType=null;
    $lastRefId=null;
    //$lastPe=$pe;
    $arrayWbs=array();
    $renumberArray=array();
    while ($line = Sql::fetchLine($result)) {
      $currentWbs=$line['wbs'];
      $wbs=$currentWbs;
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $id=$line['id'];
      $refName=$line['name'];
      $topRefType=$line['topreftype'];
      $topRefId=$line['toprefid'];
      $topId=$line['topid'];
      if ($trace) echo "$currentWbs - $refType #$refId - $refName<br/>";
      if (! $refType or ! $refId) {
        if($print)displayError(i18n("checkPlanningElementEmpty",array(i18n($refType),$refId,$id)));
        $errors++;
        if ($correct) {
          $pe=new PlanningElement($id);
          $resultDeletePE=$pe->delete();
          if (getLastOperationStatus($resultDeletePE=="OK")) {
            if($print)displayOK(i18n("checkFixed"),true);
          } else {
            if($print)displayMsg(i18n("checkNotFixed"),true);
          }
        }
        continue;
      }
      // check for duplicate WBS
      if ($currentWbs==$lastWbs) {
        if($print)displayError(i18n("checkWbsDuplicate",array(formatWbs($lastWbs),i18n($lastRefType),$lastRefId,i18n($refType),$refId)));
        $errors++;
        if ($correct) {
          $renumberArray[$topId??'*']=$wbs; // $id;
          //$pe=new PlanningElement($id);
          //self::fixOrder($pe,"duplicate",$peList,$idx,get_class($pe),$print);
        }
      }
      // Check Parent
      $parentWbs='';
      if ($topRefType and $topRefId) {
        $key=$topRefType.'#'.$topRefId;
        $parentWbs=(isset($arrayWbs[$key]))?$arrayWbs[$key]:'';
        if (!$parentWbs) { // Possibly just incorrect order
          $parentPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$topRefType, 'refId'=>$topRefId));
          if ($parentPe and $parentPe->id) {
            $parentWbs=$parentPe->wbsSortable;
          }
        }
        if ($parentWbs=='') {
          if($print)displayError(i18n("checkWbsParentNotFound",array($topRefType,$topRefId, i18n($refType), $refId)));
          $errors++;
          if ($correct) {
            $renumberArray[$topId??'*']=$wbs;
            //if($print)displayError(i18n("checkCannotFix"),true);
          }
        }
      }
      if ($parentWbs and $parentWbs!=pq_substr($wbs,0,pq_strlen($parentWbs))) {
        if($print)displayError(i18n("checkWbsParentIssue",array(formatWbs($wbs),i18n($refType),$refId,formatWbs($parentWbs),$topRefType,$topRefId)));
        $errors++;
        if ($correct) {
          $renumberArray[$topId??'*']=$wbs;
          //$pe=new PlanningElement($id);
          //self::fixOrder($pe,"parent",$peList,$idx,get_class($pe),$print);
        }
      } else if ($parentWbs and pq_strlen($wbs)!=pq_strlen($parentWbs)+6) {
        if($print)displayError(i18n("checkWbsParentIssue",array(formatWbs($wbs),i18n($refType),$refId,formatWbs($parentWbs),$topRefType,$topRefId)));
        $errors++;
        if ($correct) {
          $renumberArray[$topId??'*']=$wbs;
          //$pe=new PlanningElement($id);
          //self::fixOrder($pe,"parent",$peList,$idx,get_class($pe),$print);
        }
      }
      // Check Order
      $order=pq_substr($wbs,-5);
      if ($lastWbs==$parentWbs) { // Previous is parent, so must be 001
        if (intval($order)!=1 and ($wbs!='00000' or $refType!='Project')) {
          if($print)displayError(i18n("checkWbsFirst", array(formatWbs($wbs),i18n($refType),$refId)));
          $errors++;
          if ($correct) {
            $renumberArray[$topId??'*']=$wbs;
            //$pe=new PlanningElement($id);
            //self::fixOrder($pe,"first",$peList,$idx,get_class($pe),$print);
          }
        }
      } else if (pq_substr($lastWbs,0,-6)==$parentWbs) { // Previous has same root (same parent), number must be is sequence
        if (intval($order)!=intval(pq_substr($lastWbs,-5))+1) {
          if($print)displayError(i18n("checkWbsOrder",array(formatWbs($wbs), i18n($refType), $refId, formatWbs($lastWbs))));
          $errors++;
          if ($correct) {
            $renumberArray[$topId??'*']=$wbs;
            //$pe=new PlanningElement($id);
            //self::fixOrder($pe,"order",$peList,$idx,get_class($pe),$print);
          }
        }
      } else { // Change root, current numbering must be is sequence
        $rootPrev=pq_substr($lastWbs,0,pq_strlen($wbs));
        if (intval($order)!=intval(pq_substr($rootPrev,-5))+1) {
          if($print)displayError(i18n("checkWbsOrder",array(formatWbs($wbs), i18n($refType), $refId, formatWbs($lastWbs))));
          $errors++;
          if ($correct) {
            $renumberArray[$topId??'*']=$wbs;
            //$pe=new PlanningElement($id);
            //self::fixOrder($pe,"order",$peList,$idx,get_class($pe),$print);
          }
        }
      }
      // Check if($print)displayed wbs compared to wbsSortable
  
      // Check project order
      if ($refType=='Project') {
        $prj=new Project($refId);
        $pe=$prj->ProjectPlanningElement;
        if ($prj->sortOrder!=$wbs) {
          if($print)displayError(i18n("checkWbsSortOrderProject",array($prj->id,formatWbs($prj->sortOrder),formatWbs($wbs))));
          $errors++;
          if ($correct) {
            $prj->sortOrder=$wbs;
            $prj->simpleSave(true);
            $renumberArray[$topId??'*']=$wbs;
            //$prj->sortOrder=$wbs;
            //$res=$prj->save();
            //if (getLastOperationStatus($res)=='OK'  or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
            //else if($print)displayError($res,true);
          }
        }
  
      }
      // Continue
      $key=$refType.'#'.$refId;
      $arrayWbs[$key]=$currentWbs;
      $lastWbs=$currentWbs;
      //$lastPe=$pe;
      $lastRefType=$refType;
      $lastRefId=$refId;
    }
    if ($correct and count($renumberArray)>0) {
      debugTraceLog("=== Global renumber of WBS structure === Start ");
      foreach ($renumberArray as $key=>$wbs) {
        if ($key=='*') $key=null;
        $plan=new PlanningElement($key);
        debugTraceLog("  renumber wbs at level $plan->wbsSortable to fix WBS $wbs");
        if ($key) $msg=i18n("fixWbsStructure",array($plan->refType,$plan->refId,$plan->wbs,formatWbs($wbs)));
        else $msg=i18n("fixWbsStructure",array('Project','*','*','*'));
        if (substr($msg,0,1)=='[') $msg="fix WBS structure for $plan->refType #$plan->refId with WBS $plan->wbs to fix incorrect WBS ".formatWbs($wbs);
        $plan->renumberWbs(true);
        if($print)displayOK(i18n("checkFixed")." - ".$msg,true);
      }
      debugTraceLog("=== Global renumber of WBS structure === End ");
    }
    if (!$errors) {
      if($print) displayOK(i18n("checkNoError"));
    }
  }  
  
  private static function fixOrder($el, $issue,$elList,$idx,$class,$print=true) {
    debugTraceLog("fixOrder - $issue");
    
    if($class=="Budget"){
    	$actual = new Budget($el->id);
    	$bs = "bbs";
    	$top="idBudget";
    	$sortableField="bbsSortable";
    }else if($class=="Skill"){
    	$actual = new Skill($el->id);
    	$bs = "sbs";
    	$top="idSkill";
    	$sortableField="sbsSortable";
    }else{
    	$actual = new PlanningElement($el->id);
    	$bs = "wbs";
    	$top="topId";
    	$sortableField="wbsSortable";
    }
//     $actual=($class=="Budget")?new Budget($el->id):new PlanningElement($el->id);
//     $bs=($class=="Budget")?"bbs":"wbs";
//     $top=($class=="Budget")?"idBudget":"topId";
//     $sortableField=($class=="Budget")?"bbsSortable":"wbsSortable";
    if ($el->$sortableField!=$actual->$sortableField) {
      if($print)displayOK(i18n("checkFixed"),true);
      return;
    }
    $action="unknown";
    $elNext=null;
    $elPrec=null;
    if ($issue=="duplicate" or $issue=="parent") { // Duplicate or inconsistent with Parent => just get a good one (order is sure incorrect)
      $action="recalculate";
    } else if ($issue=="first") {
      $action="recalculateLevel";
    } else if ($issue=="order") {
      $action="recalculate";
      $cur=$idx-1;
      while ($action=="recalculate" and $cur>=0) {
        $elPrec=$elList[$cur];
        if (pq_substr($el->$sortableField,0,pq_strlen($el->$sortableField)-5)!=pq_substr($elPrec->$sortableField,0,pq_strlen($el->$sortableField)-5)) {
          $cur=-1;
          break;
        }
        if (pq_strlen($el->$sortableField)==pq_strlen($elPrec->$sortableField)) {
          $action="moveFromPrec";
        }
        $cur--;
      }
    } else {
      if($print)displayError(i18n("checkCannotFix"),true);
    }
    if(!($class=='PlanningElement' and $el->refType=="Project" and Project::isTheLeaveProject($el->refId))){
      if ($action=="recalculate" ) {
        $el->$bs=null;
        $el->$sortableField=null;
        $res=$el->save();
        if (getLastOperationStatus($res)=='OK' or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
        else if($print)displayError($res,true);
      } else if ($action=='moveFromPrec' and $elPrec) {
        $res=$el->moveTo($elPrec->id,'after');    // moveTo function
        if (getLastOperationStatus($res)=='OK' or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
        else if($print)displayError($res,true);
      } else if ($action=="recalculateLevel" and $el->$top) {
        $where="$top=".$el->$top;
        $levelList=$el->getSqlElementsFromCriteria(null,null,$where,$sortableField);
        if (count($levelList)==1) {
          $el->$bs=null;
          $el->$sortableField=null;
          $res=$el->save();
          if (getLastOperationStatus($res)=='OK' or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
          else if($print)displayError($res,true);
        } else if (count($levelList)>1) {
            $first=$levelList[0];
            $second=$levelList[1];
            $res=$second->moveTo($first->id,'before');
            $first=new $class($first->id);
            $second=new $class($second->id);
            $res=$first->moveTo($second->id,'before');
            if (getLastOperationStatus($res)=='OK' or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
            else if($print)displayError($res,true);
        }
      } else {
        if ($issue!='') {
          if($print)displayError(i18n("checkCannotFix"),true);
        }
      }
    }
  }
  
  // =================================================================================================================
  // BBS Ordering
  // =================================================================================================================
  
  /**
   * Check consistency of WBS ordering
   * @param string $if($print)display
   * @param string $correct
   */
  public static function checkBbs($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkBbs - correct BBS index in Budgets Structure");
    $budget=new Budget();
    $budgetList=$budget->getSqlElementsFromCriteria(null,null,"1=1",'bbsSortable asc');
    $lastBbs='';
    $lastBudget=$budget;
    $errors=0;
    $arrayBbs=array();
    foreach ($budgetList as $idx=>$bud) {
      $currentBbs=$bud->bbsSortable;
      if ($trace) echo "$bud->bbsSortable -Budget #$bud->id - $bud->name <br/>";

      // check for duplicate BBS
      if ($bud->bbsSortable==$lastBbs) {
        if($print)displayError(i18n("checkBbsDuplicate",array($lastBbs,$lastBudget->id,$bud->id)));
        $errors++;
        if ($correct) {
          //======= Fix order duplicate BBS ======///
          self::fixOrder($bud,"duplicate",$budgetList,$idx,get_class($bud),$print);
        }
      }
      // Check Parent
      $parentBbs='';
      if ($bud->idBudget) {
        $key=$bud->idBudget;
        $parentBbs=(isset($arrayBbs[$key]))?$arrayBbs[$key]:'';
        if (!$parentBbs) { // Possibly just incorrect order
          $parentBudget=SqlElement::getSingleSqlElementFromCriteria('Budget', array('id'=>$key));
          if ($parentBudget and $parentBudget->id) {
            $parentBbs=$parentBudget->bbsSortable;
          }
        }
        if ($parentBbs=='') {
          if($print)displayError(i18n("checkBbsParentNotFound",array($key,$bud->id)));
          $errors++;
          if ($correct) {
            if($print)displayError(i18n("checkCannotFix"),true);
          }
        }
      }
      
      if ($parentBbs and $parentBbs!=pq_substr($bud->bbsSortable,0,pq_strlen($parentBbs))) {
        if($print)displayError(i18n("checkBbsParentIssue",array($bud->bbsSortable,$bud->id,$parentBbs,$bud->idBudget)));
        $errors++;
        if ($correct) {
          //======= Fix order to parent bbs ======///
          self::fixOrder($bud,"parent",$budgetList,$idx,get_class($bud),$print);
        }
      } else if ($parentBbs and pq_strlen($bud->bbsSortable)!=pq_strlen($parentBbs)+6) {
        if($print)displayError(i18n("checkBbsParentIssue",array($bud->bbsSortable,$bud->id,$parentBbs,$bud->idBudget)));
        $errors++;
        if ($correct) {
          //======= Fix order to parent bbs ======///
          self::fixOrder($bud,"parent",$budgetList,$idx,get_class($bud),$print);
        }
      }
      // Check Order
      $order=pq_substr($bud->bbsSortable,-5);
      if ($lastBbs==$parentBbs) { // Previous is parent, so must be 001
        if (intval($order)!=1 and $bud->bbsSortable!='00000' ) {
          if($print)displayError(i18n("checkBbsFirst", array($bud->bbsSortable,$bud->id)));
          $errors++;
          if ($correct) {
            //======= Fix order, move on first position ======///
            self::fixOrder($bud,"first",$budgetList,$idx,get_class($bud),$print);
          }
        }
      } else if (pq_substr($lastBbs,0,-6)==$parentBbs) { // Previous has same root (same parent), number must be is sequence
        if (intval($order)!=intval(pq_substr($lastBbs,-5))+1) {
          if($print)displayError(i18n("checkBbsOrder",array($bud->bbsSortable, $bud->id, $lastBbs)));
          $errors++;
          if ($correct) {
            //======= Fix order wrong sequence ======///
            self::fixOrder($bud,"order",$budgetList,$idx,get_class($bud),$print);
          }
        }
      } else { // Change root, current numbering must be is sequence
        $rootPrev=pq_substr($lastBbs,0,pq_strlen($bud->bbsSortable));
        if (intval($order)!=intval(pq_substr($rootPrev,-5))+1) {
          if($print)displayError(i18n("checkBbsOrder",array($bud->bbsSortable,$bud->id,$lastBbs)));
          $errors++;
          if ($correct) {
            //======= Fix order to numbering must be is sequence ======///
            self::fixOrder($bud,"order",$budgetList,$idx,get_class($bud),$print);
          }
        }
      }
  
      // Continue
      $key=$bud->id;
      $arrayBbs[$key]=$currentBbs;
      $lastBbs=$currentBbs;
      $lastBudget=$bud;
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }
  
  // =================================================================================================================
  // SBS Ordering
  // =================================================================================================================
  
  /**
   * Check consistency of WBS ordering
   * @param string $if($print)display
   * @param string $correct
   */
  public static function checkSbs($correct=false,$trace=false,$print=true) {
  	debugTraceLog("checkSbs - correct SBS index in Skills Structure");
  	$skill=new Skill();
  	$skillList=$skill->getSqlElementsFromCriteria(null,null,"1=1",'sbsSortable asc');
  	$lastSbs='';
  	$lastSkill=$skill;
  	$errors=0;
  	$arraySbs=array();
  	foreach ($skillList as $idx=>$skl) {
  		$currentSbs=$skl->sbsSortable;
  		if ($trace) echo "$skl->sbsSortable -Skill #$skl->id - $skl->name <br/>";
  
  		// check for duplicate SBS
  		if ($skl->sbsSortable==$lastSbs) {
  			if($print)displayError(i18n("checkSbsDuplicate",array($lastSbs,$lastSkill->id,$skl->id)));
  			$errors++;
  			if ($correct) {
  				//======= Fix order duplicate SBS ======///
  				self::fixOrder($skl,"duplicate",$skillList,$idx,get_class($skl),$print);
  			}
  		}
  		// Check Parent
  		$parentSbs='';
  		if ($skl->idSkill) {
  			$key=$skl->idSkill;
  			$parentSbs=(isset($arraySbs[$key]))?$arraySbs[$key]:'';
  			if (!$parentSbs) { // Possibly just incorrect order
  				$parentSkill=SqlElement::getSingleSqlElementFromCriteria('Skill', array('id'=>$key));
  				if ($parentSkill and $parentSkill->id) {
  					$parentSbs=$parentSkill->sbsSortable;
  				}
  			}
  			if ($parentSbs=='') {
  				if($print)displayError(i18n("checkSbsParentNotFound",array($key,$skl->id)));
  				$errors++;
  				if ($correct) {
  					if($print)displayError(i18n("checkCannotFix"),true);
  				}
  			}
  		}
  
  		if ($parentSbs and $parentSbs!=pq_substr($skl->sbsSortable,0,pq_strlen($parentSbs))) {
  			if($print)displayError(i18n("checkSbsParentIssue",array($skl->sbsSortable,$skl->id,$parentSbs,$skl->idSkill)));
  			$errors++;
  			if ($correct) {
  				//======= Fix order to parent bbs ======///
  				self::fixOrder($skl,"parent",$skillList,$idx,get_class($skl),$print);
  			}
  		} else if ($parentSbs and pq_strlen($skl->sbsSortable)!=pq_strlen($parentSbs)+6) {
  			if($print)displayError(i18n("checkSbsParentIssue",array($skl->sbsSortable,$skl->id,$parentSbs,$skl->idSkill)));
  			$errors++;
  			if ($correct) {
  				//======= Fix order to parent bbs ======///
  				self::fixOrder($skl,"parent",$skillList,$idx,get_class($skl),$print);
  			}
  		}
  		// Check Order
  		$order=pq_substr($skl->sbsSortable,-5);
  		if ($lastSbs==$parentSbs) { // Previous is parent, so must be 001
  			if (intval($order)!=1 and $skl->sbsSortable!='00000' ) {
  				if($print)displayError(i18n("checkSbsFirst", array($skl->sbsSortable,$skl->id)));
  				$errors++;
  				if ($correct) {
  					//======= Fix order, move on first position ======///
  					self::fixOrder($skl,"first",$skillList,$idx,get_class($skl),$print);
  				}
  			}
  		} else if (pq_substr($lastSbs,0,-6)==$parentSbs) { // Previous has same root (same parent), number must be is sequence
  			if (intval($order)!=intval(pq_substr($lastSbs,-5))+1) {
  				if($print)displayError(i18n("checkSbsOrder",array($skl->sbsSortable, $skl->id, $lastSbs)));
  				$errors++;
  				if ($correct) {
  					//======= Fix order wrong sequence ======///
  					self::fixOrder($skl,"order",$skillList,$idx,get_class($skl),$print);
  				}
  			}
  		} else { // Change root, current numbering must be is sequence
  			$rootPrev=pq_substr($lastSbs,0,pq_strlen($skl->sbsSortable));
  			if (intval($order)!=intval(pq_substr($rootPrev,-5))+1) {
  				if($print)displayError(i18n("checkSbsOrder",array($skl->sbsSortable,$skl->id,$lastSbs)));
  				$errors++;
  				if ($correct) {
  					//======= Fix order to numbering must be is sequence ======///
  					self::fixOrder($skl,"order",$skillList,$idx,get_class($skl),$print);
  				}
  			}
  		}
  
  		// Continue
  		$key=$skl->id;
  		$arraySbs[$key]=$currentSbs;
  		$lastSbs=$currentSbs;
  		$lastSkill=$skl;
  	}
  	if (!$errors) {
  		if($print)displayOK(i18n("checkNoError"));
  	}
  }
  
  // =================================================================================================================
  // Work Duplicate
  // =================================================================================================================
  
  public static function checkDuplicateWork($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkDuplicateWork - Check for duplicates on idAssignment, idResource, refType, refId, idWorkElement");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $work=new Work();
    $workTable=$work->getDatabaseTableName();
    $query="SELECT idAssignment as idassignment, idResource as idResource, refType as reftype, refId as refid, idWorkElement as idworkelement, day as day, count(*) as cpt from $workTable group by idAssignment, idResource, refType, refId, idWorkElement, day having count(*)>1";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $idAss=$line['idassignment'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $idWork=$line['idworkelement'];
      $day=$line['day'];
      $cpt=$line['cpt'];
      $lstWork=$work->getSqlElementsFromCriteria(array('idAssignment'=>$idAss,'day'=>$day, 'refType'=>$refType, 'refId'=>$refId, 'idWorkElement'=>$idWork),null,'id asc');
      $wk=reset($lstWork);
      $resName=SqlList::getNameFromId('Affectable', $wk->idResource);
      if($print)displayError(i18n("checkDuplicateWorkFound",array($resName,htmlFormatDate($wk->workDate),i18n($wk->refType),$wk->refId)));
      $errors++;
      if ($correct) {
        $nb=0;
        $res='';
        foreach ($lstWork as $work) {
          if ($nb==0 and $work->work!=0) {
            $nb++;
            // Do not delete first not null
          } else {            
            $res=$work->delete();
          }
          
        }
        if (getLastOperationStatus($res)=='OK'  or getLastOperationStatus($res)=='NO_CHANGE') if($print)displayOK(i18n("checkFixed"),true);
        else if($print)displayError($res,true);
      }
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
      
    }
  }
  
  // =================================================================================================================
  // Work On Ticket
  // =================================================================================================================
  
  public static function checkWorkOnTicket($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkWorkOnTicket - Check work on WorkElement compared to sum of Work");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $work=new Work();
    $workTable=$work->getDatabaseTableName();
    $we=new workElement();
    $weTable=$we->getDatabaseTableName();
    $tk=new Ticket();
    $tkTable=$tk->getDatabaseTableName();
    $query="SELECT we.refType as reftype, we.refId as refid, we.realWork as realwork, (select sum(work) from $workTable w where w.idWorkElement=we.id) as sumwork from $weTable we where realwork!=(select sum(work) from $workTable w where w.idWorkElement=we.id) ";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $realWork=$line['realwork'];
      $sumWork=$line['sumwork'];
      if (Work::displayWorkWithUnit($realWork)==Work::displayWorkWithUnit($sumWork)) continue; // It is just a rounding issue
      if($print)displayError(i18n("checkIncorrectWork",array(i18n($refType),$refId,Work::displayWorkWithUnit($realWork),Work::displayWorkWithUnit($sumWork))));
      $errors++;
      if ($correct) {
        $elt=new $refType($refId);
        $res=$elt->save();
        $we=SqlElement::getSingleSqlElementFromCriteria('WorkElement', array('refType'=>$refType, 'refId'=>$refId));
        if ($we->id) {
          $we->realWork=$sumWork;
          $resWe=$we->simpleSave();
        }
        if (getLastOperationStatus($res)=='OK' or (isset($resWe) and getLastOperationStatus($resWe)=='OK') ) {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
          $query="SELECT idResource as idres, sum(work) as sumwork from $workTable w where w.refType='$refType' and w.refId=$refId group by idResource";
          $resultRes=Sql::query($query);
          while ($lineRes = Sql::fetchLine($resultRes)) {
            $idRes=$lineRes['idres'];
            $sumWork=$lineRes['sumwork'];
            if($print)displayMsg('&nbsp;-&nbsp;'.SqlList::getNameFromId('Affectable', $idRes).' : '.Work::displayWorkWithUnit($sumWork),true);
          } 
        }
      }
    }
    $query="SELECT w.id as idwork, w.refType as reftype, w.refId as refid, w.workDate as date, w.idResource as res, (select idActivity from $tkTable t where t.id=w.refId) as idact from $workTable w where w.refType='Ticket' and w.idAssignment is null and (select idActivity from $tkTable t where t.id=w.refId) is not null";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $idActivity=$line['idact'];
      $date=$line['date'];
      $workId=$line['idwork'];
      $idRes=$line['res'];
      if($print)displayError(i18n("checkIncorrectAssignmentOnTicket",array(i18n($refType),$refId,$idActivity,htmlFormatDate($date,false,false),SqlList::getNameFromId('Resource', $idRes))));
      $errors++;
      if ($correct) {
        $obj=new $refType($refId);
        $work=new Work($workId);
        $work->refType='Activity';
        $work->refId=$idActivity;
        if (!$work->idWorkElement) {
          $work->idWorkElement=$obj->WorkElement->id;
        }
        $ass=new Assignment();
        $assList=$ass->getSqlElementsFromCriteria(array('idResource'=>$idRes,'refType'=>'Activity','refId'=>$idActivity));
        if (count($assList)>0) {
          $ass=$assList[0];
          $work->idAssignment=$ass->id;
          $res=$work->save();
          if (getLastOperationStatus($res)=='OK') {
            if($print)displayOK(i18n("checkFixed"),true);
          }
        }
        
      }
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
  
    }
  }
  
  // =================================================================================================================
  // Work On Activity
  // =================================================================================================================
  
  public static function checkWorkOnActivity($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkWorkOnActivity - Check work on PlanningElement compared to sum of Work");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $work=new Work();
    $workTable=$work->getDatabaseTableName();
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $we=new WorkElement();
    $weTable=$we->getDatabaseTableName();
//     $query="SELECT pe.refType as reftype, pe.refId as refid, pe.realWork as realwork, pe.leftWork as leftwork, pe.plannedWork as plannedwork,"
//           ."  coalesce((select sum(work) from $workTable w where w.refType=pe.refType and w.refId=pe.refId),0)"
//           ."+coalesce((select sum(pesum.realWork) from $peTable pesum where pesum.topId=pe.id),0)"
//           ."+coalesce((select sum(coalesce(wesum.realWork,0)) from $weTable wesum where pe.refType='Project' and wesum.idProject=pe.refId and wesum.idActivity is null),0)"
//           ." as sumwork "
//           ."FROM $peTable pe "
//           ."WHERE pe.isManualProgress=0 and ( (pe.realWork+pe.leftWork)!=pe.plannedWork or pe.realwork!="
//            ."coalesce((select sum(work) from $workTable w where w.refType=pe.refType and w.refId=pe.refId),0)"
//            ."+coalesce((select sum(pesum.realWork) from $peTable pesum where pesum.topId=pe.id),0)"
//            ."+coalesce((select sum(coalesce(wesum.realWork,0)) from $weTable wesum where pe.refType='Project' and wesum.idProject=pe.refId and wesum.idActivity is null),0)"
//            ." )";
    $query="select * from  
              (SELECT pe.refType as reftype, pe.refId as refid, pe.realWork as realwork, pe.leftWork as leftwork, pe.plannedWork as plannedwork,
                      coalesce((select sum(work) from $workTable w where w.refType=pe.refType and w.refId=pe.refId),0) as workcurrent,
                      coalesce((select sum(pesub.realWork) from $peTable pesub where pesub.topId=pe.id),0) as worksub, 
	                    coalesce((select wes.sumwe from (select sum(we.realWork) sumwe, we.idProject projwe from $weTable we where we.idActivity is null group by idProject) wes where pe.refType='Project' and pe.refId=projwe),0) as workwe
               FROM $peTable pe) x
               WHERE x.realwork != x.workcurrent+x.worksub+x.workwe;";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $realWork=$line['realwork'];
      $leftWork=$line['leftwork'];
      $plannedWork=$line['plannedwork'];
      $sumWork=$line['workcurrent']+$line['worksub']+$line['workwe'];      
      if(!$sumWork){
        $sumWork = 0;
      }
      if (Work::displayWorkWithUnit($realWork)==Work::displayWorkWithUnit($sumWork) and Work::displayWorkWithUnit($realWork+$leftWork)==Work::displayWorkWithUnit($plannedWork)) {
        continue; // It is just a rounding issue
      } else if (abs($realWork+$leftWork-$plannedWork)<0.01) {
        continue; // It is just a rounding issue
      }
      $errorDisplayed=false;
      if (round($realWork,2)!=round($sumWork,2)) {
        if($print)displayError(i18n("checkIncorrectWork",array(i18n($refType),$refId,Work::displayWorkWithUnit($realWork),Work::displayWorkWithUnit($sumWork))));
        $errorDisplayed=true;
      }
      if (round($realWork+$leftWork,2)!=round($plannedWork,2)) {
        if($print)displayError(i18n("checkIncorrectSumWork",array(i18n($refType),$refId,Work::displayWorkWithUnit($realWork),Work::displayWorkWithUnit($leftWork),Work::displayWorkWithUnit($plannedWork))));
        $errorDisplayed=true;
      }
      if (!$errorDisplayed) {
        $msg=(pq_substr(i18n("checkUnknownError"),0,1)=='[')?"Unknown error for $refType #$refId":i18n("checkUnknownError",array(i18n($refType),$refId));
        if($print)displayError($msg);
        traceLog($msg. " at Consistency::checkWorkOnActivity() | realWork=$realWork | leftWork=$leftWork | plannedWork=$plannedWork | sumWork=$sumWork");
      }
      $errors++;
      if ($correct) {
        $res=PlanningElement::updateSynthesis($refType,$refId);
        if (getLastOperationStatus($res)!='OK') {
          if($print)displayMsg(i18n("checkNotFixed"),true);
          $query="SELECT idResource as idres, sum(work) as sumwork from $workTable w where w.refType='$refType' and w.refId=$refId group by idResource";
          $resultRes=Sql::query($query);
          while ($lineRes = Sql::fetchLine($resultRes)) {
            $idRes=$lineRes['idres'];
            $sumWork=$lineRes['sumwork'];
            if($print)displayMsg('&nbsp;-&nbsp;'.SqlList::getNameFromId('Affectable', $idRes).' : '.Work::displayWorkWithUnit($sumWork),true);
          }
        } else {
          if($print)displayOK(i18n("checkFixed"),true);
        }
      }
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
  
    }
  }
  
  // =================================================================================================================
  // Work On Activity
  // =================================================================================================================
  
  public static function checkWorkOnMeeting($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkWorkOnMeeting - Check work directly entered on Periodic Meeting");
//     if($print){
//       Sql::commitTransaction(); // Commit all what is already done as this part may rollback
//       Sql::beginTransaction();
//     }
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $work=new Work();
    $workTable=$work->getDatabaseTableName();
    $query="SELECT w.id as id, w.refType as reftype, w.refId as refid, w.idResource as idresource, w.work as work, w.workDate as workdate"
      ." FROM $workTable w "
      ." WHERE w.refType='PeriodicMeeting'";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $work=$line['work'];
      $date=$line['workdate'];
      $id=$line['id'];
      $idResource=$line['idresource'];
      $errorDisplayed=false;
      if (true) {
        $for=SqlList::getNameFromId('Resource', $idResource);
        $for.=' ('.Work::displayWorkWithUnit($work);
        $for.=', '.htmlFormatDate($date).')';
        if($print)displayError(i18n("checkIncorrectWorkOnMeeting",array(i18n($refType),$refId,$for)));
        $errorDisplayed=true;
      }
      $errors++;
      if ($correct) {
        $meet=SqlElement::getSingleSqlElementFromCriteria('Meeting', array('idPeriodicMeeting'=>$refId, 'meetingDate'=>$date));
        if (!$meet or ! $meet->id) {
          $meet=new Meeting();
          $meetList=$meet->getSqlElementsFromCriteria(null,null,"idPeriodicMeeting=$refId and meetingDate>='$date'","meetingDate asc");
          if (count($meetList)==0) $meetList=$meet->getSqlElementsFromCriteria(null,null,"idPeriodicMeeting=$refId and meetingDate<='$date'","meetingDate desc");
          $meet=reset($meetList);
        }
        if ($meet and $meet->id) {
          $ass=SqlElement::getSingleSqlElementFromCriteria('Assignment', array('refType'=>'Meeting', 'refId'=>$meet->id, 'idResource'=>$idResource));
          if (!$ass->id) { // No Assignment => will create one
            $res=new Resource($idResource);
            $ass->idResource=$idResource;
            $ass->refType='Meeting';
            $ass->refId=$meet->id;
            $ass->idProject=$meet->idProject;
            $ass->rate=100;
            $ass->idRole=$res->idRole;
            $ass->idle=$meet->idle;
            $resSaveAss=$ass->save();
          }
          if ($ass and $ass->id) {
            $wOld=new Work($id);
            $wNew=SqlElement::getSingleSqlElementFromCriteria('Work', array('refType'=>'Meeting', 'refId'=>$meet->id, 'idResource'=>$idResource,'idAssignment'=>$ass->id,'workDate'=>$date));
            if ($wNew and $wNew->id) {
              $wNew->work+=$work;
            } else {
              $wNew=clone($wOld);
              $wNew->id=null;
              $wNew->refType='Meeting';
              $wNew->refId=$meet->id;
              $wNew->idAssignment=$ass->id;
            }
            $resOld=$wOld->delete();
            $resNew=$wNew->saveForced();
            $ass->saveWithRefresh();
            if (getLastOperationStatus($resNew)=='OK' and getLastOperationStatus($resOld)=='OK') {
              if($print){
                displayOK(i18n("checkFixed"),true);
                Sql::commitTransaction();
                Sql::beginTransaction();
              }
            } else {
              traceLog("Delete old work on Periodic Meeting : $resOld");
              traceLog("Create new work on Meeting : $resNew");
              if($print){
                displayMsg(i18n("checkNotFixed").' (error on update)',true);
                Sql::rollbackTransaction();
                Sql::beginTransaction();
              }
            }
          } else {
            if($print)displayMsg(i18n("checkNotFixed").' (assignment not found)',true);
          }
        } else {
          if($print)displayMsg(i18n("checkNotFixed").' (meeting not found)',true);
        }
      }
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
  
    }
  }
  // =================================================================================================================
  // Work On Assignment
  // =================================================================================================================
  
  public static function checkWorkOnAssignment($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkWorkOnAssignment - Check work on Assignment compared to sum of Work");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $work=new Work();
    $workTable=$work->getDatabaseTableName();
    $ass=new Assignment();
    $assTable=$ass->getDatabaseTableName();
    $query="SELECT ass.id as id, ass.refType as reftype, ass.refId as refid, ass.realWork as realwork, ass.leftWork as leftwork, ass.plannedWork as plannedwork,"
        ."  (select sum(work) from $workTable w where w.idAssignment=ass.id) as sumwork, ass.idResource as idresource "
        ."FROM $assTable ass "
        ."WHERE realwork!=(select sum(work) from $workTable w where w.idAssignment=ass.id) "
        ."   OR (coalesce(ass.realWork,0)+coalesce(ass.leftWork,0))!=coalesce(ass.plannedWork,0) ";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $id=$line['id'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $realWork=$line['realwork'];
      $leftWork=$line['leftwork'];
      $plannedWork=$line['plannedwork'];
      $idResource=$line['idresource'];
      $sumWork=$line['sumwork'];
      if (Work::displayWorkWithUnit($realWork)==Work::displayWorkWithUnit($sumWork) and Work::displayWorkWithUnit($realWork+$leftWork)==Work::displayWorkWithUnit($plannedWork)) continue; // It is just a rounding issue
      if ($realWork!=$sumWork) if($print)displayError(i18n("checkIncorrectWork",array(i18n($refType),$refId,Work::displayWorkWithUnit($realWork),Work::displayWorkWithUnit($sumWork))));
      if ($realWork+$leftWork!=$plannedWork) if($print)displayError(i18n("checkIncorrectSumWork",array(i18n($refType),$refId.' ['.i18n('Resource').' #'.$idResource.']',Work::displayWorkWithUnit($realWork),Work::displayWorkWithUnit($leftWork),Work::displayWorkWithUnit($plannedWork))));
      $errors++;
      if ($correct) {
        $ass=new Assignment($id);
        $res=$ass->saveWithRefresh();
        if (getLastOperationStatus($res)!='OK') {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        } else {
          if($print)displayOK(i18n("checkFixed"),true);
        }
      }
    }
    // Check Resource 
    debugTraceLog("checkWorkOnAssignment - Check Resource on Work compared to Resource on Assignment");
    $res=new Resource();
    $resTable=$res->getDatabaseTableName();
    $query="SELECT a.id as assid, a.idResource as assress, w.id as workid, w.idResource as workres, w.workDate as workdate, w.refType as reftype, w.refid as refid "
        ." FROM $workTable w, $assTable a, $resTable r "
        ." where w.idAssignment=a.id and a.idResource=r.id and r.isResourceTeam=0 and a.idResource!=w.idResource";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $wRes=SqlList::getNameFromId('Affectable', $line['workres']);
      $aRes=SqlList::getNameFromId('Affectable', $line['assress']);
      $date=htmlFormatDate($line['workdate']);
      if($print)displayError(i18n('errorWorkResource',array($wRes,$aRes,$date,$line['workid'],$line['assid'],i18n($line['reftype']),$line['refid'])));
      $errors++;
      if ($correct) {
        $w=new Work($line['workid']);
        $w->idResource=$line['assress'];
        $res=$w->save();
        if (getLastOperationStatus($res)!='OK') {
          if($print)displayMsg(i18n("checkNotFixed"),true);
          debugTraceLog($res);
        } else {
          if($print)displayOK(i18n("checkFixed"),true);
        }
      }
    }
    debugTraceLog("checkWorkOnAssignment - Check Work with no project");
    // Check work with no project
    $query="SELECT w.id as id, w.idAssignment as assid, w.refType as reftype, w.refId as refid"
        ." FROM $workTable w "
        ." WHERE w.idProject is null or w.idProject=0 ";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $id=$line['id'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $assid=$line['assid'];
      if($print)displayError(i18n('checkWorkWithoutProject',array($id,i18n($refType),$refId)));
      $errors++;
      if ($correct) {
        $w=new Work($id);
        $proj=null;
        $ass=new Assignment($assid);
        if ($ass->idProject) {
          $proj=$ass->idProject;
        } else if ($refType and $refId) {
          $obj=new $refType($refId);
          if (property_exists($obj, 'idProject') and $obj->idProject) {
            $proj=$obj->idProject;
          }
        }
        if ($proj) {
          $w->idProject=$proj;
          $res=$w->save();
        } else if (! $refType and ! $refId) {
          $res=$w->delete();
        } else {
          $res="No Project found for Assignment #$assid and for $refType #$refId";
        }
        if (getLastOperationStatus($res)!='OK') {
          if($print)displayMsg(i18n("checkNotFixed"),true);
          debugTraceLog($res);
        } else {
          if($print)displayOK(i18n("checkFixed"),true);
        }
      }
    }  
    debugTraceLog("checkWorkOnAssignment - Check Work with no resource or not existing resource");
    $query="SELECT w.id as id, w.idResource as idres, w.idAssignment as idass, w.refType as reftype, w.refid as refid"
        ." FROM $workTable w LEFT JOIN $resTable res ON res.id = w.idResource"
        ." WHERE w.idResource IS NULL OR w.idResource = 0 OR res.id IS NULL OR w.refType IS NULL OR w.refId IS NULL;";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $id=$line['id'];
      $idres=$line['idres'];
      $idass=$line['idass'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $w=new Work($id);
      if($print)displayError(i18n("checkInvalidReferenceOnWork",array($id,$idres,$refType,$refId)));
      $errors++;
      if ($correct) {
        $ass=new Assignment($idass);
        if ($ass->id and $ass->idResource and $ass->refType and $ass->refId) {
          $res=new Affectable($idres);
          if ($res->id) {
            $w->idResource=$ass->idResource;
            if (!$refType or !$refId) {
              $w->refType=$ass->refType;
              $w->refId=$ass->refId;
            }
            $res=$w->save();
            $ass->saveWithRefresh();
          } else {
            $res=$w->delete();
            $ass->delete();
          }
        } else {
          $res=$w->delete();
        }
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    } 
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
  
    }
  }
  
  // =================================================================================================================
  // Idle consistency from Activity / PlanningElement / Assignment
  // =================================================================================================================
  
  public static function checkIdlePropagation($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkIdlePropagation - Check idle propagation");
    $errors=0;
    
    debugTraceLog("checkIdlePropagation - Check idle on PlanningElement compared to idle on Activity, Meeting or TestSession");
    // Direct Query : valid here for technical needs on grouping
    $actArray=array('Activity','Meeting','TestSession');
    foreach ($actArray as $type) {
      $ass=new Assignment();
      $assTable=$ass->getDatabaseTableName();
      $act=new $type();
      $actTable=$act->getDatabaseTableName();
      $pe=new PlanningElement();
      $peTable=$pe->getDatabaseTableName();
      $query="SELECT act.id as actid, pe.id as peid, ass.id as assid, act.idle as actidle, pe.idle as peidle, ass.idle as assidle "
          ." FROM $actTable as act left join $peTable as pe on (pe.refType='$type' and pe.refId=act.id) left join $assTable ass on (ass.refType='$type' and ass.refId=act.id)"
          ." WHERE act.idle!=pe.idle or (act.idle!=ass.idle and ass.idle is not null and act.idle=1)";
      $result=Sql::query($query);
      while ($line = Sql::fetchLine($result)) {
        $actId=$line['actid'];
        $peId=$line['peid'];
        $assId=$line['assid'];
        $actIdle=$line['actidle'];
        $peIdle=$line['peidle'];
        $assIdle=$line['assidle'];
        if($print)displayError(i18n("checkIncorrectIdle",array(i18n($type),$actId,$actIdle,$peIdle,$assIdle)));
        $errors++;
        if ($correct) {
          if ($assId) {
            $ass=new Assignment($assId);
            $ass->idle=$actIdle;
            if ($ass->idle==1) $ass->leftWork=0;
            $resAss=$ass->save();
          }
          if ($peId) {
            $pe=new PlanningElement($peId);
            $pe->idle=$actIdle;
            if ($pe->idle==1) $pe->leftWork=0;
            $resPe=$pe->save();
          }
          $act=new $type($actId);
          $resAct=$act->save();
          if (getLastOperationStatus($resAct)=='OK' or (isset($resPe) and getLastOperationStatus($resPe)=='OK') or (isset($resAss) and getLastOperationStatus($resAss)=='OK') ) {
            if($print)displayOK(i18n("checkFixed"),true);
          } else {
            if($print)displayMsg(i18n("checkNotFixed"),true);
          }
        }
      }
    }
    
    debugTraceLog("checkIdlePropagation - Check non idle PlanningElement under idle Parent PlanningElement");
    // Direct Query : valid here for technical needs on grouping
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $query="SELECT pe.id, pe.refType as reftype, pe.refId as refid, top.refType as topreftype, top.refId as toprefid "
          ."FROM $peTable pe left join $peTable top on pe.topId=top.id "
          ."WHERE pe.idle=0 and top.idle=1";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $id=$line['id'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $topRefType=$line['topreftype'];
      $topRefId=$line['toprefid'];
      if($print)displayError(i18n("checkIncorrectIdleParent",array(i18n($refType),$refId,i18n($topRefType),$topRefId)));
      $errors++;
      if ($correct) {
        $act=new $refType($refId);
        $act->idle=1; // must close the non closed item
        $resAct=$act->save();
        if (getLastOperationStatus($resAct)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }
  
  // =================================================================================================================
  // Missing (or Extra) Planning Elements
  // =================================================================================================================
  
  public static function checkMissingPlanningElement($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkMissingPlanningElement - Plannable items that have no or more than 1 PlanningElement");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $work=new Work();
    $workTable=$work->getDatabaseTableName();
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $ass=new Assignment();
    $assTable=$ass->getDatabaseTableName();
    
    $query="SELECT ass.refType as reftype, ass.refId as refid, ass.idResource as idresource, ass.id as id from $assTable ass"
         . "  WHERE (select count(*) from $peTable pe where pe.refType=ass.refType and pe.refId=ass.refId )!=1";
    $result=Sql::query($query);
    $stockRefType='';
    $stockRefId='';
    while ($line = Sql::fetchLine($result)) {
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $assId=$line['id'];
      if ($refType==$stockRefType and $refId==$stockRefId) continue;
      $stockRefType=$refType;
      $stockRefId=$refId;
      $listPe=$pe->getSqlElementsFromCriteria(array('refType'=>$refType,"refId"=>$refId));
      if (count($listPe)==0) {
        if($print)displayError(i18n("checkPlanningElementMissing",array(i18n($refType),$refId)));
        $errors++;
        if ($correct) {
          $peNameForRefObj=$refType."PlanningElement";
          $pmNameForRefObj="id".$refType."PlanningMode";
          $refObjFromPlan=new $refType($refId);
          if ($refObjFromPlan->id) { // Assignment refers to existing item
            if (property_exists($refObjFromPlan,$peNameForRefObj) and is_object($refObjFromPlan->$peNameForRefObj)
            and property_exists($refObjFromPlan->$peNameForRefObj, $pmNameForRefObj) and !$refObjFromPlan->$peNameForRefObj->$pmNameForRefObj) {
              $planningModeList=SqlList::getList('PlanningMode','applyTo');
              foreach ($planningModeList as $pmId=>$pmApplyTo) {
                if ($pmApplyTo==$refType) {
                  $refObjFromPlan->$peNameForRefObj->$pmNameForRefObj=$pmId;
                  break;
                }
              }
            }
            $resultSaveObjFromPlan=$refObjFromPlan->save();
            if (getLastOperationStatus($resultSaveObjFromPlan=="OK")) {
              if($print)displayOK(i18n("checkFixed"),true);
            } else {
              if($print)displayMsg(i18n("checkNotFixed"),true);
            }
          } else { // Assignment refers to no existing item : delete
            $ass=new Assignment($assId);
            if ($ass->id) {
            	$resultDeleteInvalidAssignement=$ass->delete();
              if (getLastOperationStatus($resultDeleteInvalidAssignement=="OK")) {
                if($print)displayOK(i18n("checkFixed"),true);
              } else {
                if($print)displayMsg(i18n("checkNotFixed"),true);
              }
            } else {
            	if($print)displayMsg(i18n("checkNotFixed"),true);
            }
          }
        }
      } else {
        if($print)displayError(i18n("checkPlanningElementExtra",array(i18n($refType),$refId,count($listPe))));
        $errors++;
        if ($correct) {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    
    $act=new Activity();$actTable=$act->getDatabaseTableName();
    $pro=new Project();$proTable=$pro->getDatabaseTableName();
    $mil=new Milestone();$milTable=$mil->getDatabaseTableName();
    $met=new Meeting();$metTable=$met->getDatabaseTableName();
    $pme=new PeriodicMeeting();$pmeTable=$pme->getDatabaseTableName();
    $tst=new TestSession();$tstTable=$tst->getDatabaseTableName();
    debugTraceLog("checkMissingPlanningElement - PlanningElement refering to not existing item (Activity, Project, Milestone, Periodic Meeeting or TestSession)");
    $query ="SELECT pe.refType as reftype, pe.refId as refid, pe.id as id from $peTable pe"
          . "  WHERE pe.refType='Activity' and not exists (select 'x' from $actTable x where x.id=pe.refId)";
    $query.=" UNION "; 
    $query.="SELECT pe.refType as reftype, pe.refId as refid, pe.id as id from $peTable pe"
          . "  WHERE pe.refType='Project' and not exists (select 'x' from $proTable x where x.id=pe.refId)";
    $query.=" UNION ";
    $query.="SELECT pe.refType as reftype, pe.refId as refid, pe.id as id from $peTable pe"
          . "  WHERE pe.refType='Milestone' and not exists (select 'x' from $milTable x where x.id=pe.refId)";
    $query.=" UNION ";
    $query.="SELECT pe.refType as reftype, pe.refId as refid, pe.id as id from $peTable pe"
          . "  WHERE pe.refType='Meeting' and not exists (select 'x' from $metTable x where x.id=pe.refId)";
    $query.=" UNION ";
    $query.="SELECT pe.refType as reftype, pe.refId as refid, pe.id as id from $peTable pe"
          . "  WHERE pe.refType='PeriodicMeeting' and not exists (select 'x' from $pmeTable x where x.id=pe.refId)";
    $query.=" UNION ";
    $query.="SELECT pe.refType as reftype, pe.refId as refid, pe.id as id from $peTable pe"
          . "  WHERE pe.refType='TestSession' and not exists (select 'x' from $tstTable x where x.id=pe.refId)";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $id=$line['id'];
      $pe=new PlanningElement($id);
      if ($pe->id) {
        if($print)displayError(i18n("checkPlanningElementEmpty",array(i18n($refType),$refId,$id)));
        $errors++;
        if ($correct) {
          $resultDeleteInvalidPlanningElement=$pe->delete();
          if (getLastOperationStatus($resultDeleteInvalidPlanningElement=="OK")) {
            if($print)displayOK(i18n("checkFixed"),true);
          } else {
            if($print)displayMsg(i18n("checkNotFixed"),true);
          }
        }
      } 
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }
  
  // =================================================================================================================
  // Budget
  // =================================================================================================================
    
  public static function checkBudget($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkBudget - Compare amounts on budget with sum of amounts of expenses");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $bud=new Budget();
    $budTable=$bud->getDatabaseTableName();
    $exp=new Expense();
    $expTable=$exp->getDatabaseTableName();
    $query="SELECT bud.id as idbudget, bud.usedAmount as usedamount, bud.usedFullAmount as usedfullamount,"
        ." bud.billedAmount as billedamount, bud.billedFullAmount as billedfullamount,"
        ." sum(exp.plannedAmount) as sumplannedamount, sum(exp.realAmount) as sumrealamount,"
        ." sum(exp.plannedFullAmount) as sumplannedfullamount, sum(exp.realFullAmount) as sumrealfullamount"
        ." FROM $budTable bud, $expTable exp"
        ." WHERE bud.elementary=1 and bud.id=exp.idBudgetItem and exp.cancelled=0"
        ." GROUP BY bud.id, bud.usedAmount, bud.usedFullAmount,bud.billedAmount, bud.billedFullAmount"
        ." HAVING bud.usedAmount<>sum(exp.plannedAmount) or bud.usedFullAmount<>sum(exp.plannedFullAmount)"
        ." or bud.billedAmount<>sum(exp.realAmount) or bud.billedFullAmount<>sum(exp.realFullAmount)";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $idBudget=$line['idbudget'];
      $cause="";
      if ($line['usedamount']!=$line['sumplannedamount']) {
        $cause=i18n("colIdBudget")." ".$bud->getColCaption('usedAmount'). " (".$line['usedamount'].") <> "
              .i18n('sum').' '.i18n("colExpense")." ".$exp->getColCaption('plannedAmount'). " (".$line['sumplannedamount'].")";
        if($print)displayError(i18n("checkIncorrectBudgetAmounts",array($idBudget,$cause)));
      }
      if ($line['usedfullamount']!=$line['sumplannedfullamount']) {
        $cause=i18n("colIdBudget")." ".$bud->getColCaption('usedFullAmount'). " (".$line['usedfullamount'].") <> "
              .i18n('sum').' '.i18n("colExpense")." ".$exp->getColCaption('plannedFullAmount'). " (".$line['sumplannedfullamount'].")";
        if($print)displayError(i18n("checkIncorrectBudgetAmounts",array($idBudget,$cause)));
      }
      if ($line['billedamount']!=$line['sumrealamount']){
        $cause=i18n("colIdBudget")." ".$bud->getColCaption('billedAmount'). " (".$line['billedamount'].") <> "
              .i18n('sum').' '.i18n("colExpense")." ".$exp->getColCaption('realAmount'). " (".$line['sumrealamount'].")";
        if($print)displayError(i18n("checkIncorrectBudgetAmounts",array($idBudget,$cause)));
      }
      if ($line['billedfullamount']!=$line['sumrealfullamount']) {
        $cause=i18n("colIdBudget")." ".$bud->getColCaption('billedFullAmount'). " (".$line['billedfullamount'].") <> "
              .i18n('sum').' '.i18n("colExpense")." ".$exp->getColCaption('realFullAmount'). " (".$line['sumrealfullamount'].")";
        if($print)displayError(i18n("checkIncorrectBudgetAmounts",array($idBudget,$cause)));
      }
      
      $errors++;
      if ($correct) {
        $bud=new Budget($idBudget);
        $res=$bud->save();
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
  
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
  
    }
  }
  // =================================================================================================================
  // Idle consistency from Activity / PlanningElement / Assignment
  // =================================================================================================================
  
  public static function checkInvalidFilters($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkInvalidFilters - Check filters with criteria on list with value 0");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $crit=new FilterCriteria();
    $critTable=$crit->getDatabaseTableName();
    $filter=new Filter();
    $filterTable=$filter->getDatabaseTableName();
    $query="SELECT crit.id as idcrit, crit.dispAttribute as attribute, filter.name as name, filter.refType as reftype, filter.idUser as user "
        ." FROM $critTable crit, $filterTable filter"
        ." WHERE crit.idFilter=filter.id and crit.sqlOperator='IN' and crit.sqlValue='0' and crit.isDynamic=0";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $type=$line['reftype'];
      $userName=SqlList::getNameFromId('Affectable', $line['user']);
      $attribute=$line['attribute'];
      $filterName=$line['name'];
      $id=$line['idcrit'];
      if($print)displayError(i18n("checkIncorrectFilterCriteria",array($filterName,i18n($type),$userName,$attribute)));
      $errors++;
      if ($correct) {
        $fc=new FilterCriteria($id);
        $res=$fc->delete();
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }

    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
  
    }
    
  }
  
  // Check pools
  public static function checkPools($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkPools - Check pools including not existing resource");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $res=new Resource();
    $resTable=$res->getDatabaseTableName();
    $rta=new ResourceTeamAffectation();
    $rtaTable=$rta->getDatabaseTableName();
    $query="SELECT rta.id as id, rta.idResourceTeam as idpool, rta.idResource as idres"
        ." FROM $rtaTable rta"
        ." WHERE (rta.idResource is null or rta.idResource=0 or not exists (select'x' from $resTable res where res.id=rta.idResource) )";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $idpool=$line['idpool'];
      $idres=$line['idres'];
      $id=$line['id'];
      $poolItem=new ResourceTeam($idpool); 
      $pool="#".$poolItem->id." - ".$poolItem->name;
      if($print)displayError(i18n("checkInvalidPoolAllocation",array($pool,$idres)));
      $errors++;
      if ($correct) {
        $rta=new ResourceTeamAffectation($id);
        $res=$rta->delete();
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
  
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }
  
  public static function checkProject($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkProject - Check Project consistency");
    // Direct Queries : valid here for technical needs on grouping
    
    $errors=0;
    $projects=array();
    
    debugTraceLog("checkProject - Check Project on Planning Element for Activity compared to Project on Parent");
    $pe=new PlanningElement(); $peTable=$pe->getDatabaseTableName();
    $query="SELECT pe.id idpe, pe.refType element, pe.refId id, pe.idProject idproject, top.idProject parentidproject, top.refId toprefid "
        ."FROM $peTable pe left join $peTable top on top.id=pe.topId "
        ."WHERE pe.refType!='Project' and pe.topRefType is not null and pe.topRefId is not null and pe.idProject!=top.idProject;";
    $reqAct=Sql::query($query);
    while ($line = Sql::fetchLine($reqAct)) {
      $class=$line['element'];
      $id=$line['id'];
      $idPe=$line['idpe'];
      $proj=$line['idproject'];
      $topProj=$line['parentidproject'];
      $topRefId=$line['toprefid'];
      if($print)displayError(i18n("checkProjectInvalid",array($proj,i18n($class).' #'.$id, $topProj, i18n('colParentActivity').' #'.$topRefId)));
      $errors++;
      if ($correct) {
        $projects[$proj]=$proj;
        $projects[$topProj]=$topProj;
        $item=new $class($id);
        $item->idProject=$topProj;
        $res1=$item->simpleSave();
        $item=new PlanningElement($idPe);
        $item->idProject=$topProj;
        $res2=$item->simpleSave();
        if (getLastOperationStatus($res1)=='OK' or getLastOperationStatus($res2)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    

    
    //
    debugTraceLog("checkProject - Check Project on Assignment compared to Project on PlanningElement");
    // Direct Query : valid here for technical needs on grouping
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $as=new Assignment();
    $asTable=$as->getDatabaseTableName();
    //$query="SELECT a.id, a.idProject as idproject, a.refType as reftype, a.refId as refid from $asTable a where a.idProject <> ( select idProject from $peTable pe where pe.refType=a.refType and pe.refId=a.refId)";
    $query="SELECT ass.id as id, ass.idProject idproject, ass.refType reftype, ass.refId refid, pe.idProject peidproject " 
          ."FROM $asTable ass left join $peTable pe on ass.refType=pe.refType and ass.refId=pe.refId "
          ."WHERE pe.idProject!=ass.idProject";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $id=$line['id'];
      $idProject=$line['idproject'];
      $peIdProject=$line['peidproject'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $obj=new $refType($refId);
      if($print)displayError(i18n("checkProjectInvalid",array($idProject,i18n('Assignment').' #'.$id, $obj->idProject,i18n($refType).' #'.$refId)));
      $errors++;
      if ($correct) {
        $projects[$idProject]=$idProject;
        $projects[$peIdProject]=$peIdProject;
        $as=new Assignment($id);
        $as->idProject=$obj->idProject;
        $res=$as->saveForced();
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    
    debugTraceLog("checkProject - Check Project on Work compared to Project on Assignment");
    $wk=new Work();
    $wkTable=$wk->getDatabaseTableName();
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $as=new Assignment();
    $asTable=$as->getDatabaseTableName();
    //$query="SELECT w.id, w.idProject as idproject, w.refType as reftype, w.refId as refid from $wkTable w where w.idProject <> ( select idProject from $peTable pe where pe.refType=w.refType and pe.refId=w.refId)";
    $query="SELECT w.id, w.idProject as idproject, w.refType as reftype, w.refId as refid, ass.idProject assidproject "
          ."FROM $wkTable w left join $asTable ass on ass.id=w.idAssignment "
          ."WHERE w.idAssignment is not null and w.idProject!=ass.idProject";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $id=$line['id'];
      $idProject=$line['idproject'];
      $assIdProject=$line['assidproject'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $obj=new $refType($refId);
      if($print)displayError(i18n("checkProjectInvalid",array($idProject,i18n('Work').' #'.$id, $obj->idProject,i18n($refType).' #'.$refId)));
      $errors++;
      if ($correct) {
        $projects[$idProject]=$idProject;
        $projects[$assIdProject]=$assIdProject;
        $w=new Work($id);
        $w->idProject=$obj->idProject;
        $res=$w->saveForced();
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    
    if ($correct) {
      debugTraceLog("checkProject - Update Projects Synthesis");
      foreach ($projects as $idP) {
        //$pe=SqlElement::getSingleSqlElementFromCriteria('ProjectPlanningElement', array('refType'=>'Project','refId'=>$idP));
        //if (!$pe->id) continue;
        $res=PlanningElement::updateSynthesis('Project',$idP);
        //echo "Project #$idP - updateSynthesis<br/>";
      }
    }
    
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }
  
  public static function checkPeriodicMeetingAssign($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkPeriodicMeetingAssign - Check Assignement on Periodic Meeting must be closed, with not left work ");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $as=new Assignment();
    $asTable=$as->getDatabaseTableName();
    $query="SELECT a.id, a.idProject as idproject, a.idResource as idresource, a.refType as reftype, a.refId as refid, a.idle as idle, a.leftWork as leftwork
              from $asTable a where a.refType='PeriodicMeeting' and (a.idle<>1 or a.leftWork is not null or a.leftWork<>0)";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $asError=false;
      $id=$line['id'];
      $idProject=$line['idproject'];
      $refType=$line['reftype'];
      $refId=$line['refid'];
      $ilde=$line['idle'];
      $leftwork=($line['leftwork'])?intval($line['leftwork']):0;
      $resource=SqlList::getNameFromId('Resource', $line['idresource']);
      $obj=new $refType($refId);
      if($ilde!=1){
        $asError=true;
        $errors++;
        if($print)displayError(i18n("checkPeriodicMeetingAssignInvalidIdle",array($resource ,$refId,$idProject)));
      }
      if($leftwork>0){
        $asError=true;
        $errors++;
        if($print)displayError(i18n("checkPeriodicMeetingAssignInvalidLeftWork",array($resource ,$refId,$idProject)));
      }
      
      if ($correct and $asError) {
        $assignment=new Assignment($id);
        $assignment->idle=1;
        $assignment->leftWork=0;
        $assignment->plannedWork=$assignment->realWork+$assignment->leftWork;
        $res=$assignment->saveForced();
        if (getLastOperationStatus($res)=='OK') {
          if($print)displayOK(i18n("checkFixed"),true);
        } else {
          if($print)displayMsg(i18n("checkNotFixed"),true);
        }
      }
    }
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }

  public static function checkDependencyLoop($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkDependencyLoop - Check infinite dependency loop");
    $errors=0;
    // Direct Query : valid here for technical needs on grouping
    $dep=new Dependency();
    $depTable=$dep->getDatabaseTableName();
    $query="SELECT d.predecessorId as pred, d.successorId as succ, d.dependencyType as type, d.dependencyDelay as delay from $depTable d ";
    $result=Sql::query($query);
    $depLines=array();
    while ($line = Sql::fetchLine($result)) {
      $keyPrec='|'.$line['pred'].'|';
      $keySucc='|'.$line['succ'].'|';
      if (!isset($depLines[$keyPrec])) $depLines[$keyPrec]=$keySucc;
      foreach($depLines as $tmpId=>$tmpDepLine) {
        if (strpos($tmpDepLine,$keySucc)) {
          if($print) displayError("ERROR");
          $pePrec=new PlanningElement(trim($keyPrec,'|'));
          $peSucc=new PlanningElement(trim($keySucc,'|'));
          if($print) displayError(i18n("checkDependencyLoop",array($pePrec->refType.' #'.$pePrec->refId ,$peSucc->refType.' #'.$peSucc->refId)));
          errorLog("Dependency Loop Found");
          $lineItems=explode('|',trim(str_replace('||','|',$tmpDepLine),'|'));
          foreach ($lineItems as $item) {
            $pe=new PlanningElement($item);
            errorLog("   PË #$item - $pe->refType=>$pe->refId");
          }
          //break;
        }
        if (strpos($tmpDepLine,$keyPrec)) {
          $depLines[$tmpId]=$tmpDepLine.$keySucc;
        }
      }
    }
    foreach($depLines as $key=>$depLine) {
      displayOK("$key => $depLine");
    }
  }
  
  public static function checkAssignmentSelection($correct=false,$trace=false,$print=true) {
    debugTraceLog("checkAssignmentSelection - AssignmentSelection for assignments with uniqueResource");
    $errors=0;
    $ass=new Assignment();$assTable=$ass->getDatabaseTableName();
    $sel=new AssignmentSelection();$selTable=$sel->getDatabaseTableName();
    $rta=new ResourceTeamAffectation();$rtaTable=$rta->getDatabaseTableName();
    $table=array();
    
    // Search for Resource in AssignmentSelection that is not in Pool
    $query="select ass.id as assId, ass.refType, ass.refId, ass.idResource "
         . " from $selTable sel, $assTable ass "
         . " where sel.idAssignment=ass.id "
         . "   and not exists (select 'x' from $rtaTable rst where rst.idResourceTeam=ass.idResource and rst.idResource=sel.idResource)";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $assId=$line['assId']??$line['assid'];
      $table[$assId]=$assId;
    }
    $query="select ass.id as assId, ass.refType, ass.refId, ass.idResource, rst.idResource as manquant "
         . " from $rtaTable rst, $assTable ass "
         . " where rst.idResourceTeam=ass.idResource and ass.isResourceTeam=1 and ass.uniqueResource=1 and rst.idle=0 "
         . "   and not exists (select 'x' from $selTable sel where sel.idResource=rst.idResource and sel.idAssignment=ass.id)";
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $assId=$line['assId']??$line['assid'];
      $table[$assId]=$assId;
    }
    
    $assList=$ass->getSqlElementsFromCriteria(array("uniqueResource"=>1));
    foreach ($table as $assId) {
      $ass=new Assignment($assId);
      if($print) displayError(i18n("checkAssignmentSelection",array($ass->id, $ass->refType, $ass->refId, $ass->idResource)));
      $errors++;
      if ($correct){
        $res=AssignmentSelection::addResourcesFromPool($ass->id,$ass->idResource,-1);
        if (getLastOperationStatus($res)=='OK'and $print) displayOK(i18n("checkFixed"),true);
      }
    }   
    if (!$errors) {
      if($print)displayOK(i18n("checkNoError"));
    }
  }
  
  public static function checkSubTaskProject($correct=false, $trace=false, $print=true) {
    debugTraceLog("checkSubTaskProject - Check SubTask project consistency with parent element");
    $errors = 0;
    
    $sub = new SubTask(); $subTable = $sub->getDatabaseTableName();
    
    $refTypes = array(
        'Ticket' => (new Ticket())->getDatabaseTableName(),
        'UserStory' => (new UserStory())->getDatabaseTableName(),
        'Activity' => (new Activity())->getDatabaseTableName(),
    );
    
    foreach ($refTypes as $refType => $parentTable) {
      $query = "SELECT s.id as id, s.idProject as idproject, s.refType as reftype, s.refId as refid, p.idProject as parentidproject "
          . "FROM $subTable s "
          . "LEFT JOIN $parentTable p ON s.refType='$refType' AND s.refId=p.id "
          . "WHERE s.refType='$refType' "
          . "  AND p.id IS NOT NULL "
          . "  AND s.idProject != p.idProject";
      $result = Sql::query($query);
      while ($line = Sql::fetchLine($result)) {
        $id = $line['id'];
        $idProject = $line['idproject'];
        $parentProject = $line['parentidproject'];
        $refId = $line['refid'];
        if ($print) displayError(i18n("checkSubTaskProjectInvalid", array($idProject, $id, $parentProject, i18n($refType), $refId)));
          $errors++;
          if ($correct) {
            $s = new SubTask($id);
            $s->idProject = $parentProject;
            $res = $s->saveForced();
            if (getLastOperationStatus($res) == 'OK') {
              if ($print) displayOK(i18n("checkFixed"), true);
            } else {
              if ($print) displayMsg(i18n("checkNotFixed"), true);
            }
          }
       }
    }
    
    if (!$errors) {
      if ($print) displayOK(i18n("checkNoError"));
    }
  }
}
?>