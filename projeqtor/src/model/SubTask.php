<?php
use Doctrine\Common\Cache\Version;
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : Julien PAPASIAN
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
 * Habilitation defines right to the application for a menu and a profile.
 */
require_once('_securityCheck.php');

class SubTask extends SqlElement {

  public $id;    
  public $refType;
  public $refId;
  public $idProject;
  public $idTargetProductVersion;
  public $sortOrder;
  public $name;
  public $idPriority;
  public $idResource;
  public $dueDate;
  public $paused;
  public $handled;
  public $done;
  public $idle;
  public $creationDateTime;
  public $idUser;


  

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
  // DRAW SUBTASK
  // ============================================================================**********
  static function drawSubtasksForObject($obj,$refType, $refId,$rightUpdate,$rightRead,$refresh=false,$idResource=false,$gloablView=false,$dialogView=false,$onlyHisSubTask=false,$idPriority=false,$orderBy=null){
    global $cr, $print, $user, $comboDetail, $printWidth;
    $paramScreen=Parameter::getUserParameter('paramScreen');
    $paramObjectDetail=Parameter::getUserParameter('paramLayoutObjectDetail');
    $paramColDueDateseparate=false;
    $paramColDueDateseparate = ($paramScreen == 'left') ? false : (($paramObjectDetail == 'col') ? false : true);
    $attach= new Attachment();
//     if ($comboDetail or (!$rightUpdate and !$rightRead) or ($rightUpdate=='NO' and $rightRead=='NO')) {
//       return;
//     }
    if ((!$rightUpdate and !$rightRead) or ($rightUpdate=='NO' and $rightRead=='NO')) return;
    
    if(!$gloablView ) $view='Single';
    else $view='Global';
    $showClosedSubTask=(Parameter::getUserParameter('showClosedSubTask_'.$view)!='' and Parameter::getUserParameter('showClosedSubTask_'.$view)!='0')?true:false;
    $showDoneSubTask=((Parameter::getUserParameter('showDoneSubTask_'.$view)!='0') or $showClosedSubTask==true)?true:false;
    $subTask=new SubTask();
    $assignment= new Assignment();
    $crit=array("refType"=>$refType,"refId"=>$refId,"done"=>"0","idle"=>"0");
    if($showDoneSubTask){
      $crit=array("refType"=>$refType,"refId"=>$refId,"idle"=>"0");
    }
    if($showClosedSubTask){
      $crit=array("refType"=>$refType,"refId"=>$refId);
    }
    
    if($idResource!=false and $idResource!=0){
      $val=array("idResource"=>$idResource);
      $crit=array_merge($crit,$val);
    }else if($onlyHisSubTask){
      $val=array("idResource"=>$user->id);
      $crit=array_merge($crit,$val);
    }
    if($idPriority!=0){
      $val=array("idPriority"=>$idPriority);
      $crit=array_merge($crit,$val);
    }
    $res=$subTask->getSqlElementsFromCriteria($crit,false,null,'sortOrder');
    $critFld='idProject';
    $critVal=$obj->idProject;
    $widthDisplay=(RequestHandler::isCodeSet("destinationWidth")?RequestHandler::getValue("destinationWidth"):"");
    if(!$gloablView and !$print){
      $priority=new Priority();
      $allPrio=$priority->getSqlElementsFromCriteria(null,null,"1=1");
      foreach ($allPrio as $id=>$priority){
        echo '<input id="colorPrio_'.$priority->id.'" value="'.$priority->color.'" type="hidden" />';
      }
    }
    if($dialogView) echo '<table>';
    if (!$print and !$gloablView and !$dialogView and !$refresh) {
      echo'<div style="position:absolute;right:5px;top:3px;">';
      echo' <label for="showClosedSubTask_'.$view.'"  class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;height:'.((isNewGui())?'20':'10').'px;width:'.((isNewGui())?'50':'150').'px">'.i18n('labelShowIdle'.((isNewGui())?'Short':'')).'&nbsp;</label>';
      echo' <div class="'.((isNewGui())?"whiteCheck":"").'" id="showClosedSubTask_'.$view.'" style="'.((isNewGui())?'margin-top:14px':'').'" dojoType="dijit.form.CheckBox" type="checkbox" '.(($showClosedSubTask)?'checked':'');
      echo'   title="'.i18n('labelShowIdle').'" >';
      echo'   <script type="dojo/connect" event="onChange" args="evt">';
      echo'     saveUserParameter("showClosedSubTask_'.$view.'",((this.checked)?"1":"0"));';
      echo'     if (checkFormChangeInProgress()) {return false;}';
      echo'     loadContent("objectDetail.php", "detailDiv", "listForm");';
      echo'   </script>';
      echo' </div>';
      echo'</div>';
      echo'<div style="position:absolute;right:'.((isNewGui())?"110px":"200px").';top:3px;">';
      echo' <label for="showDoneSubTask_'.$view.'"  class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;height:'.((isNewGui())?'20':'10').'px;width:'.((isNewGui())?'50':'150').'px">'.i18n('done').'&nbsp;</label>';
      echo' <div class="'.((isNewGui())?"whiteCheck":"").'" id="showDoneSubTask_'.$view.'" style="'.((isNewGui())?'margin-top:14px':'').'" dojoType="dijit.form.CheckBox" type="checkbox"  '.(($showDoneSubTask)?'checked':'').' '.(($showClosedSubTask)?'readonly':'');
      echo' title="'.i18n('done').'" >';
      echo'   <script type="dojo/connect" event="onChange" args="evt">';
      echo'     saveUserParameter("showDoneSubTask_'.$view.'",((this.checked)?"1":"0"));';
      echo'     if (checkFormChangeInProgress()) {return false;}';
      echo'     loadContent("objectDetail.php", "detailDiv", "listForm");';
      echo'   </script>';
      echo' </div>';
      echo'</div>';
    }
    if(!$print){
      if (!$refresh) echo '<tr><td colspan="4">
          <div id="'.$refType.'_'.$refId.'_drawSubTask" dojotype="dijit.layout.ContentPane" >' ;
      echo '<table style="width:100%;margin-top: 10px;" dojotype="dojo.dnd.Source" dndType="subTask_'.$refType.'_'.$refId.'" withhandles="true"  class="SubTaskTab"
                    id="dndSubTask_'.$refType.'_'.$refId.'" jsId="dndSubTask_'.$refType.'_'.$refId.'" data-dojo-id="test">';
      if(!$gloablView)echo '<input id="refreshSTDivValues" value="" type="hidden"/>';
    }else {
      $subTaskPrintWidth=($printWidth)?intval($printWidth).'px':'100%';
      echo '<tr><td colspan="2" style="width:'.$subTaskPrintWidth.';">';
      echo '<table style="width:'.$subTaskPrintWidth.';">';
    }
    if(!$print){
      if($gloablView and $idResource!=''){
        echo      '<input id="SubTaskIdResourceFilter_'.$refType.'_'.$refId.'" value="'.$idResource.'" type="hidden" />';
      }
      else if (property_exists($obj, 'idResource')){
        echo      '<input id="SubTaskIdResourceFilter_'.$refType.'_'.$refId.'" value="'.$obj->idResource.'" type="hidden" />';
      }
    }
    if(!$print and !$gloablView){
      echo      '<input id="subTaskView" value="'.$view.'" type="hidden" />';
      echo      '<input id="subTaskViewMaxFileSize" value="'.Parameter::getGlobalParameter('paramAttachmentMaxSize').'" type="hidden" />';
    }
    echo  '<tr style="width:100%">';
    if(!$print)echo    '<td class="linkHeader" style="width:2%"></td>';
    echo    '<td class="linkHeader" style="'.(($print)?'width:60%;':(($gloablView and $widthDisplay>='1530')?'width:64%;':'width:55%;')).'">'.i18n('colName').'</td>';
    if (($view!='Single' or $paramColDueDateseparate) and !$print){
      echo    '<td class="linkHeader" style="'.(($gloablView and $widthDisplay>='1530')?'width:12%;':'width:15%;').'">'.i18n('colPriority').'</td>';
      echo    '<td class="linkHeader" style="'.(($gloablView and $widthDisplay>='1530')?'width:12%;':'width:10%;').'">'.i18n('colDueDate').'</td>';
    }else {
      echo    '<td class="linkHeader" style="'.(($gloablView and $widthDisplay>='1530')?'width:12%;':'width:15%;').'">'.i18n('colPriority').' / '.i18n('colDueDate') .'</td>';
    }
    echo    '<td class="linkHeader" style="'.(($gloablView and $widthDisplay>='1530')?'width:12%;':'width:15%;').'">'.i18n('colResponsible').'</td>';
    echo    '<td class="linkHeader" style="'.(($gloablView and $widthDisplay>='1530')?'width:8%;':'width:10%;').';min-width:95px;">'.i18n('colIdStatus').'</td>';
    echo  '</tr>';
    if(!empty($res)){
      if ($orderBy == 'name') {
        usort($res, function ($a, $b) {
          return strcasecmp($a->name, $b->name);
        });
      } else if($orderBy =='dueDate'){
        usort($res, function ($a, $b) {
          $dateA = !empty($a->dueDate) ? strtotime($a->dueDate) : PHP_INT_MAX;
          $dateB = !empty($b->dueDate) ? strtotime($b->dueDate) : PHP_INT_MAX;
          return $dateA - $dateB;
        });
      } else if ($orderBy == 'idPriority'){
        usort($res, function ($a, $b) {
          return $b->idPriority - $a->idPriority;
        });
      } else if ($orderBy == 'status'){
        usort($res, function ($a, $b) {
          $statusOrderA = (!$a->paused && !$a->handled && !$a->done && !$a->idle) ? 0 
                        : ($a->paused ? 1
                        : ($a->handled ? 2 
                        : ($a->done ? 3 
                        : 4)));
          $statusOrderB = (!$b->paused && !$b->handled && !$b->done && !$b->idle) ? 0 
                        : ($b->paused ? 1
                        : ($b->handled ? 2 
                        : ($b->done ? 3 
                        : 4)));
        return $statusOrderA - $statusOrderB;
        });
      } else if ($orderBy == 'idResource'){
        usort($res, function ($a, $b) {
          $resourceA = new Resource($a->idResource);
          $resourceB = new Resource($b->idResource);
          if (empty($resourceA->name) && !empty($resourceB->name)) {
            return 1;  
          } elseif (!empty($resourceA->name) && empty($resourceB->name)) {
            return -1; 
          }
          if (empty($resourceA->name) && empty($resourceB->name)) {
            return 0;
          }
          return strcasecmp($resourceA->name, $resourceB->name);
        });
      }
      foreach ($res as $id=>$subTask){
        $creatorName = ($subTask->idUser) ? SqlList::getNameFromId('Affectable', $subTask->idUser) : '';
        $creationDate = ($subTask->creationDateTime) ? htmlFormatDateTime($subTask->creationDateTime, false) : '';
        $hasCreationData = !empty($subTask->creationDateTime);
      
        $prioSubTask=new Priority($subTask->idPriority);
        $colorPrio=$prioSubTask->color;
        if(!$print){
          echo  '<tr  id="'.$refType.'_'.$refId.'_subTaskRow_'.$subTask->id.'" '.(($rightUpdate=='NO' and $rightRead=='YES')?'':'class="dojoDndItem subTaskRow" dndType="subTask_'.$refType.'_'.$refId.'"').'   
                    ondragover="hideShowDropDiv(\'show\',\''.$refType.'_'.$refId.'_subTaskRow_'.$subTask->id.'\');" 
                        ondrop="hideShowDropDiv(\'dropHide\',\''.$refType.'_'.$refId.'_subTaskRow_'.$subTask->id.'\');"
                        ondragLeave="hideShowDropDiv(\'hide\',\''.$refType.'_'.$refId.'_subTaskRow_'.$subTask->id.'\');">';
          echo      '<input id="sortOrder_'.$refType.'_'.$refId.'_'.$subTask->id.'" value="'.$subTask->sortOrder.'" type="hidden" />';
          if($rightUpdate=='NO' and $rightRead=='YES'){
            echo   '<td class="todoListTab" id="'.$refType.'_'.$refId.'_grabDive_0" >&nbsp;</td>';
          }else{
            echo    '<td  class="dojoDndHandle handleCursor todoListTab"  style="text-align: center;"><img style="width:7px;top:4px;position: relative;" src="css/images/iconDrag.gif"></td>';
          }
          
          echo    '<td class="todoListTab" style="white-space:nowrap;width:auto;margin-right:5px;text-align: center;" >';
          echo    '  <table style="width:100%;"><tr><td style="'.(($gloablView and $widthDisplay>='1530')?"width:96%;":"width:90%;" ).'">';
            echo      '<textarea title="'.i18n('colName').'" id="'.$refType.'_'.$refId.'_nameNewSubTask_'.$subTask->id.'" name="'.$refType.'_'.$refId.'_nameNewSubTask_'.$subTask->id.'" 
                        dojoType="dijit.form.Textarea" style="width:98%;max-height:150px !important;" ';
            if ($rightUpdate=='NO' and $rightRead=='YES'){
              echo ' readonly="true">';
            }else {
              echo 'onChange="updateSubTask('.$subTask->id.',\''.$refType.'\','.$refId.');"  >';
            }         
            //$text = new Html2Text ($subTask->name);
            //$name = $text->getText ();
            //$name=htmlspecialchars($name);
            $name=$subTask->name;
            echo      $name .'</textarea>';
            echo    '</td><td style="'.(($gloablView and $widthDisplay>='1530')?"width:4%;":"width:10%;" ).'">';
            echo      '<div dojoType="dijit.form.Button" showlabel="false" title="'. i18n('extraButtonsBar'). '"  iconClass="dijitButtonIcon dijitButtonIconExtraButtons imageColorNewGui" class="detailButton"';
 		    echo      ' id="'.$subTask->id.'_extraButtonsDetail" onClick="showExtraButtons(\''.$subTask->id.'_extraButtonsDetail\');extraButtonDetailCurrent=\''.$subTask->id.'_extraButtonsDetail\';" ></div>';
            
            
            echo     '<div style="position:relative;left:34px;top:-32px;">'
                      .'<div class="todoListTab statusBar" id="'.$subTask->id.'_extraButtonsDetailDiv" onclick="hideExtraButtons(\''.$subTask->id.'_extraButtonsDetail\');"'
                      .'style="display:none;position:absolute;background:var(--color-background) !important;border:1px solid  #AAAAAA;z-index:99;">';
            echo     '  <table><tr>';
              if($rightUpdate=='YES'){
                echo '<td><a title="'.i18n('addAttachment').'"> '; 
                echo ' <div dojoType="dojox.form.Uploader" type="file" 
                            id="'.$subTask->id.'_attachmentFile" name="'.$subTask->id.'_attachmentFile" 
                            MAX_FILE_SIZE="'.Parameter::getGlobalParameter('paramAttachmentMaxSize').'"
  			                url="../tool/saveAttachment.php?attachmentRefType='.get_class($subTask).'&attachmentRefId='.$subTask->id.'&nameDiv='.$subTask->id.'_attachmentFile'.Security::addTokenIndexToUrl().'" 
  			                multiple="true" class="directAttachment detailButton divAttachSubTask" 
  			                uploadOnSelect="true" 
  			                target="resultPost" 

                        onBegin="if(typeof saveAttachment !== \'undefined\') { saveAttachment(true,\''.$subTask->id.'_attachmentFile\'); } else if(window.top.saveAttachment) { window.top.saveAttachment(true,\''.$subTask->id.'_attachmentFile\'); } else { showWait(); }"

  			                iconClass="iconAttachFiles" 
  			                onError="dojo.style(dojo.byId(\'downloadProgress\'), {display:\'none\'});" 
  			                style="display:inline-block;margin-left:6px;" label="" >';
                echo ' <script type="dojo/connect" event="onComplete" args="dataArray">
                          refreshSubTaskAttachment('.$subTask->id.');
                          if(typeof saveAttachmentAck !== "undefined") {
                            saveAttachmentAck(dataArray);
                          } else if(window.top.saveAttachmentAck) {
                            window.top.saveAttachmentAck(dataArray);
                          } 
                       </script>';
                echo ' <script type="dojo/connect" event="onProgress" args="data">
                        if(typeof saveAttachmentProgress !== "undefined") {
                          saveAttachmentProgress(data);
                        } else if(window.top.saveAttachmentProgress) {
                          window.top.saveAttachmentProgress(data);
                        }
                      </script>';
    	           echo '  <script type="dojo/connect" event="onError" args="data"> hideWait();showError(i18n("uploadUncomplete")); </script>';
                echo '</div> ';
                echo '</a></td>';
              }
              if (!$comboDetail){
                echo    '  <td>';
                echo    '    <button id="'.$subTask->id.'_copyButtonSubTask"   dojoType="dijit.form.Button"  showlabel="false" iconClass="dijitButtonIcon dijitButtonIconCopy imageColorNewGui" class="detailButton">';
                echo    '      <script type="dojo/connect" event="onClick" args="evt"> ';
                //              echo    '        hideResultDivs(\''.$subTask->id.'_extraButtonsDetailDiv\');';
                echo    '        copySubTaskObjectBox("'.get_class($subTask).'",'.$subTask->id.');';
                
                echo    '      </script> ';
                echo    '    </button> ';
                echo    '  </td>';
                echo    '  <td></td>';
              }
                echo    '  <td>';
              
             echo    '    <button id="'.$subTask->id.'_deleteSubTask"   dojoType="dijit.form.Button"  showlabel="false" iconClass="dijitButtonIcon dijitButtonIconDelete imageColorNewGui" class="detailButton">';
             echo    '      <script type="dojo/connect" event="onClick" args="evt"> ';
//              echo    '        hideResultDivs(\''.$subTask->id.'_extraButtonsDetailDiv\');';
             echo    '        deleteSubTask('.$subTask->id.',\''.$subTask->refType.'\','.$subTask->refId.','.json_encode($name).')';
             echo    '      </script> ';
             echo    '    </button> ';
             echo    '  </td>';
             echo    '</tr></table>';
             echo    '</div></div>';
              
              
            echo    '</td></tr><tr><td>';
              echo    '<div id="divAttachement_'.$subTask->id.'" style="width:90%;margin:0% 5%;" dojotype="dijit.layout.ContentPane">';
                        $allAttach=$attach->getSqlElementsFromCriteria(array("refType"=>get_class($subTask),"refId"=>$subTask->id),null);
                        if(!empty($allAttach)){
                          foreach ($allAttach as $attachment){
                            if ($attachment->isThumbable()) {
                              echo '<div style="float:left;" oncontextmenu="event.preventDefault();removeAttachment('.$attachment->id.');dojo.byId(\'refreshSTDivValues\').value=\''.$subTask->id.'\';">';
                              echo '<img src="'.getImageThumb($attachment->getFullPathFileName(), 32).'" '.' title="'.htmlEncode($attachment->fileName).'" 
                                    style="min-height:18px;max-width:50px;float:left;cursor:pointer;margin-left: 5px;margin-right: 5px;border:'.((isNewGui())?'1px solid var(--color-button-background-selected)':'1px solid black').'"'
                                    .((!$print)?' onClick="showImage(\'Attachment\',\''.htmlEncode($attachment->id).'\',\''.htmlEncode($attachment->fileName, 'protectQuotes').'\');"':'')
                                    .' />';
                              echo '</div>';
                            }else{
                              echo '<div style="float:left;" oncontextmenu="event.preventDefault();removeAttachment('.$attachment->id.');dojo.byId(\'refreshSTDivValues\').value=\''.$subTask->id.'\';">';
                              echo htmlGetMimeType($attachment->mimeType, $attachment->fileName, $attachment->id,'Attachment',null,28);
                              echo '</div>';
                            }
                          }
                        }
              echo'    </div>';
          echo    '  </td></tr></table>';
          echo    '</td>';
          
          
          if ($view!='Single' or $paramColDueDateseparate){
            echo    '<td class="todoListTab" style="white-space:nowrap;text-align: center;background-color:'.$colorPrio.';">';
            echo      '<select dojoType="dijit.form.FilteringSelect"  id="'.$refType.'_'.$refId.'_priorityNewSubTask_'.$subTask->id.'" name="'.$refType.'_'.$refId.'_priorityNewSubTask_'.$subTask->id.'" style="width:auto;" class="input" '.autoOpenFilteringSelect().'';
            if ($rightUpdate=='NO' and $rightRead=='YES'){
              echo ' readonly="true">';
            }else {
              echo 'onChange="updateSubTask('.$subTask->id.',\''.$refType.'\','.$refId.',\'true\',\'false\');"  >';
            }
            htmlDrawOptionForReference('idPriority',$subTask->idPriority);
            echo      '</select>';
            echo    '</td>';
            
            echo '<td class="todoListTab">';
            echo    '<div  dojoType="dijit.form.DateTextBox"  id="'.$refType.'_'.$refId.'_dueDateNewSubTask_'.$subTask->id.'" name="'.$refType.'_'.$refId.'_dueDateNewSubTask_'.$subTask->id.'"
                      invalidMessage="' . i18n('messageInvalidDate') . '" type="text" maxlength="10"
                      style="width:auto; margin:3px; text-align: center;" class="input" hasDownArrow="true"
                      constraints="{datePattern:browserLocaleDateFormatJs}"
                      value="'.$subTask->dueDate.'"';
            if ($rightUpdate == 'NO' && $rightRead == 'YES') {
              echo ' readonly="true">';
            } else {
              echo ' onChange="updateSubTask(' . $subTask->id . ',\'' . $refType . '\',' . $refId . ',\'true\',\'false\');">';
            }
            echo   '</div>';
            echo '</td>';      
          }else {
            echo    '<td class="todoListTab" style="white-space:nowrap;text-align: center;background-color:'.$colorPrio.';">';
            echo      '<div style="margin-left:3px;">';
            echo        '<select dojoType="dijit.form.FilteringSelect"  id="'.$refType.'_'.$refId.'_priorityNewSubTask_'.$subTask->id.'" name="'.$refType.'_'.$refId.'_priorityNewSubTask_'.$subTask->id.'" style="width:auto;" class="input" '.autoOpenFilteringSelect().'';
            if ($rightUpdate=='NO' and $rightRead=='YES'){
              echo ' readonly="true">';
            }else {
              echo 'onChange="updateSubTask('.$subTask->id.',\''.$refType.'\','.$refId.',\'true\',\'false\');"  >';
            }
            htmlDrawOptionForReference('idPriority',$subTask->idPriority);
            echo        '</select>';
            echo      '</div>';
            echo      '<div  dojoType="dijit.form.DateTextBox"  id="'.$refType.'_'.$refId.'_dueDateNewSubTask_'.$subTask->id.'" name="'.$refType.'_'.$refId.'_dueDateNewSubTask_'.$subTask->id.'"
                        invalidMessage="' . i18n('messageInvalidDate') . '" type="text" maxlength="10"
                        style="width:auto; margin:3px; text-align: center;" class="input" hasDownArrow="true"
                        constraints="{datePattern:browserLocaleDateFormatJs}"
                        value="'.$subTask->dueDate.'"';
            if ($rightUpdate == 'NO' && $rightRead == 'YES') {
              echo ' readonly="true">';
            } else {
              echo ' onChange="updateSubTask(' . $subTask->id . ',\'' . $refType . '\',' . $refId . ',\'true\',\'false\');">';
            }
            echo      '</div>';
            echo    '</td>';  	          
          }
          
          echo '<td class="todoListTab" style="white-space:nowrap;text-align:center; height:100%;">';
          
          echo '<div style="display:flex; flex-direction:column; justify-content:space-between; min-height:58px; height:100%;">';
          
          echo '<div style="margin-top:-2px;">';
          echo   '<select dojoType="dijit.form.FilteringSelect" id="'.$refType.'_'.$refId.'_resourceNewSubTask_'.$subTask->id.'" name="'.$refType.'_'.$refId.'_resourceNewSubTask_'.$subTask->id.'" style="width:auto; margin-bottom: 7px; margin-left:2px;
" class="input" '.autoOpenFilteringSelect().' ';
          
          if ($rightUpdate=='NO' and $rightRead=='YES'){
            echo ' readonly="true" >';
          } else {
            echo ' onChange="updateSubTask('.$subTask->id.',\''.$refType.'\','.$refId.',false,true);" >';
          }
          
          		htmlDrawOptionForReference('idResource',$subTask->idResource,$obj,false,$critFld,$critVal);
          
          echo '</select>';
          echo '</div>';
          
          if ($hasCreationData) {
            echo '<div style="font-size:85%; color:#666; text-align:center;">';
            echo '<div style="min-height:14px;">'.i18n('createBy').'</div>';
            echo '<div style="min-height:16px; display:flex; align-items:center; justify-content:center;" id="'.$refType.'_'.$refId.'_createNameUser_'.$subTask->id.'"><b>'.htmlEncode($creatorName).'</b></div>';
            echo '</div>';
          }
          
          echo '</div>';
          echo '</td>';
          
          //_________________________________________________________________________________________________
          
          echo '<td class="todoListTab" style="white-space:nowrap;text-align:center;height:100%;">';
          
          echo '<div style="display:flex; flex-direction:column; justify-content:space-between; height:100%;">';
          
          // --- STATUS ---
          echo '<div>';
          $subTask->drawStatusSubTask($subTask->id, $subTask->done, $subTask->idle, $subTask->handled, $subTask->paused, $refType, $refId, $gloablView, $rightUpdate, $rightRead, $onlyHisSubTask, $subTask->idResource);
          echo '</div>';
          
          // --- DATE ---
          if ($hasCreationData) {
            echo '<div style="font-size:85%; color:#666; text-align:center;">';
            echo '<div style="min-height:14px;margin-top:5px;">'.i18n('colCreateDateTime').'</div>';
            echo '<div style="min-height:16px; display:flex; align-items:center; justify-content:center;margin-left:5px;margin-right:5px;" id="'.$refType.'_'.$refId.'_createDate_'.$subTask->id.'"><b>'.htmlFormatDateTime($creationDate).'</b></div>';
            echo '</div>';
          }
          echo '</div>';
          echo '</td>';
          
          $lastSortRegist=$subTask->sortOrder;
        
        }else{
          $resource= new Resource();
          $namePrio=($subTask->idPriority!='' )?SqlList::getNameFromId(get_class($prioSubTask), $subTask->idPriority):'';
          $nameResource=($subTask->idResource!='' )?SqlList::getNameFromId(get_class($resource), $subTask->idResource):'';
          $backgroundColor="";
          $i18n=' ';
          if($subTask->paused==1){
            $backgroundColor="background-color:#E0E0E0;";
            $i18n=i18n('subTaskStatusOnHold');
          }else if($subTask->handled==1){
            $backgroundColor="background-color:#FACA77;";
            $i18n=i18n('colHandled');
          }else if($subTask->done==1){
            $backgroundColor="background-color:#57CE44;";
            $i18n=i18n('done');
          }else if($subTask->idle==1){
            $backgroundColor="background-color:#B7B3A9;";
            $i18n=i18n('colIdle');
          }
          $prioStyle=(pq_trim($colorPrio)!='')?'background-color:'.$colorPrio.';color:'.getForeColor($colorPrio).';':'';
          echo  '<tr>';
          echo   '<td class="assignData" >'.($subTask->name).'</td>';
          echo    '<td class="assignData" style="white-space:nowrap;text-align: center;'.$prioStyle.'" >';
          echo      '<span>'.htmlEncode($namePrio).'</span>';
          echo      '<br><span>'.($subTask->dueDate).'</span>';
          echo    '</td>';
          echo    '<td class="assignData"   style="white-space:nowrap;text-align: center;">'.htmlEncode($nameResource).'</td>';
          echo    '<td class="assignData" style="white-space:nowrap;text-align: center;'.$backgroundColor.'">'.htmlEncode($i18n).'</td>';
          echo  '</tr>';
        }
      }
    }
    if($rightUpdate=='YES' and !$print and !$onlyHisSubTask){
      $lastSort=(!empty($res))? $lastSortRegist :0;
      echo  '<tr id="'.$refType.'_'.$refId.'_newSubTaskRow" >';
      echo      '<input id="sortOrder_'.$refType.'_'.$refId.'_0" value="'.$lastSort.'" type="hidden" />';
       echo   '<td class="todoListTab" id="'.$refType.'_'.$refId.'_grabDive_0" >&nbsp;</td>';
      echo    '<td class="todoListTab" style="white-space:nowrap;text-align: center;" >';
      echo    ' <table style="width:100%;"><tr><td style="'.(($gloablView and $widthDisplay>='1530')?"width:96%;":"width:90%;" ).'">';
        echo      '<textarea title="'.i18n('colName').'" id="'.$refType.'_'.$refId.'_nameNewSubTask_0" name="'.$refType.'_'.$refId.'_nameNewSubTask_0" 
                    dojoType="dijit.form.Textarea" style="width:98%;max-height:150px !important;" 
                    maxlength="4000"  onChange="updateSubTask(0,\''.$refType.'\','.$refId.');" value="">';
        echo      '</textarea>';
      echo    ' </td><td style="'.(($gloablView and $widthDisplay>='1530')?"width:4%;":"width:10%;" ).'">';
      echo      '<div dojoType="dijit.form.Button" showlabel="false" title="'. i18n('extraButtonsBar'). '"  iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton"';
      echo      ' id="'.$refType.'_'.$refId.'_extraButtonsDetail_0" style="display:none;" ></div>';
      
      echo      '<div style="position:relative;left:34px;top:-32px;">'
                .'<div class="statusBar" id="'.$refType.'_'.$refId.'_extraButtonsDetailDiv_0" style="display:none;position:absolute;background:var(--color-background) !important;border:1px solid  #AAAAAA;z-index:99;">';
      echo    ' <table><tr>';
        if($rightUpdate=='YES'){
          echo '<td><a  style="display:none;" title="'.i18n('addAttachment').'">';
            echo ' <div dojoType="dojox.form.Uploader" type="file" id="'.$refType.'_'.$refId.'_attachmentFiles_0" id="'.$refType.'_'.$refId.'_attachmentFiles_0"  style="display:none;" label="">';		 
            echo '</div> ';
          echo '</a></td>';
        }
      echo    '  <td>';
      echo    '    <button id="'.$refType.'_'.$refId.'_copyButtonSubTask_0"  dojoType="dijit.form.Button" iconClass="dijitButtonIcon dijitButtonIconCopy" class="detailButton">';
      echo    '    </button> ';
      echo    '  </td>';
      echo    '  <td></td>';
      echo    '  <td>';
      echo    '    <button id="'.$refType.'_'.$refId.'_deleteSubTask_0"   dojoType="dijit.form.Button"  showlabel="false" iconClass="dijitButtonIcon dijitButtonIconDelete" class="detailButton">';
      echo    '    </button> ';
      echo    '  </td>';
      echo    ' </tr></table>';
      echo    ' </div></div>';
      echo    ' </td></tr><tr><td>';
      echo    '   <div id="'.$refType.'_'.$refId.'_divAttachement_0" style="width:90%;margin:0% 5%;" dojotype="dijit.layout.ContentPane"></div>';
      echo    '  </td></tr></table>';
      echo    '</td>';
      
      if ($view!='Single' or $paramColDueDateseparate){
        echo    '<td class="todoListTab" style="white-space:nowrap;text-align: center;">';
        echo      '<select dojoType="dijit.form.FilteringSelect" id="'.$refType.'_'.$refId.'_priorityNewSubTask_0" style="width:auto;"  class="input" readonly="true" >';
                    htmlDrawOptionForReference('idPriority',null);
        echo      '</select>';
        echo    '</td>';
        echo    '<td class="todoListTab">';
        echo      '<div dojoType="dijit.form.DateTextBox"  id="'.$refType.'_'.$refId.'_dueDateNewSubTask_0" style="width:auto; margin:3px; text-align: center;"
                      invalidMessage="' . i18n('messageInvalidDate') . '" type="text" maxlength="10"
                      class="input" hasDownArrow="true" readonly="true"
                      constraints="{datePattern:browserLocaleDateFormatJs}"';
        echo      '</div>';
        echo    '</td>';
      }else{
        echo    '<td class="todoListTab" style="white-space:nowrap;text-align: center;">';
        echo      '<div style="margin-left:3px;">';
        echo        '<select dojoType="dijit.form.FilteringSelect" id="'.$refType.'_'.$refId.'_priorityNewSubTask_0" style="width:auto;"  class="input" readonly="true" >';
                      htmlDrawOptionForReference('idPriority',null);
        echo        '</select>';
        echo      '</div>';
        echo      '<div dojoType="dijit.form.DateTextBox"  id="'.$refType.'_'.$refId.'_dueDateNewSubTask_0" style="width:auto; margin:3px; text-align: center;"
                      invalidMessage="' . i18n('messageInvalidDate') . '" type="text" maxlength="10"
                      class="input" hasDownArrow="true" readonly="true"
                      constraints="{datePattern:browserLocaleDateFormatJs}"';
        echo      '</div>';
        echo    '</td>'; 
      }
      
      echo      '<td class="todoListTab" style="white-space:nowrap;text-align:center; height:100%;">';
      echo        '<div style="display:flex; flex-direction:column; justify-content:space-between; height:100%;">';
      echo          '<div style="margin-top:-2px">';
      echo            '<select dojoType="dijit.form.FilteringSelect" id="'.$refType.'_'.$refId.'_resourceNewSubTask_0" style="width:auto; margin-bottom:7px; margin-left:2px;" class="input" readonly="true">';
                         htmlDrawOptionForReference('idResource',null,$obj,false,$critFld,$critVal);
      echo            '</select>';
      echo          '</div>';
      
      echo          '<div id="'.$refType.'_'.$refId.'_createNameUserBlock_0" style="font-size:85%; color:#666; text-align:center; visibility:hidden;">';
      echo            '<div style="min-height:14px;">'.i18n('createBy').'</div>';
      echo            '<div style="min-height:16px; display:flex; align-items:center; justify-content:center;" id="'.$refType.'_'.$refId.'_createNameUser_0"><b></b></div>';
      echo          '</div>';
      echo        '</div>';
      echo      '</td>';
      
      echo      '<td class="todoListTab" style="white-space:nowrap;text-align:center;height:100%;">';
      echo        '<div style="display:flex; flex-direction:column; justify-content:space-between; height:100%;">';
      echo          '<div>';
                      $subTask->drawStatusSubTask('0','0','0','0','0',$refType,$refId,$gloablView,$rightUpdate,$rightRead,false);
      echo          '</div>';
      
      echo          '<div id="'.$refType.'_'.$refId.'_createDateBlock_0" style="font-size:85%; color:#666; text-align:center; display:none;">';
      echo            '<div style="min-height:14px;margin-top: 5px;">'.i18n('colCreateDateTime').'</div>';
      echo            '<div style="min-height:16px; display:flex; align-items:center; justify-content:center;" id="'.$refType.'_'.$refId.'_createDate_0"><b></b></div>';
      echo          '</div>';
      echo        '</div>';
      echo      '</td>';
    }
    echo '</table>';
    if(!$print){
      if (!$refresh) {
        echo '</div>';
        echo '</td></tr>';
      }
      if($dialogView) echo '</table>';
    }else{
      echo '</td></tr>';
    }
  }
  
  function drawStatusSubTask($id, $done, $idle, $handled, $paused,$refType,$refId,$gloablView,$rightUpdate,$rightRead,$onlyHisSubTask,$res=false){
    global $user;
    $pos=1;
    $backgroundColor="";
    if($paused==1){
      $pos=2;
      $backgroundColor="background-color:#E0E0E0;";
    }else if($handled==1){
      $pos=3;
      $backgroundColor="background-color:#FACA77;";
    }else if($done==1){
      $pos=4;
      $backgroundColor="background-color:#57CE44;";
    }else if($idle==1){
      $pos=5;
      $backgroundColor="background-color:#B7B3A9;";
    }
    if($onlyHisSubTask or ($res and $user->id==$res and $rightUpdate!='YES' ) ){
      $rightUpdate='YES';
    }
    
    echo '<div id="'.$refType.'_'.$refId.'_slidContainer_'.$id.'" >';
    echo '<table style="width:100%;height:75%;">';
      echo '<tr>';
        echo ' <td style="width:12%;height:100%;">';
        echo '<div id="'.$refType.'_'.$refId.'_prev_'.$id.'" class="prev todoList" style="'.(($id==0 or ($done==0 && $idle==0 && $handled==0 && $paused==0) or ($rightUpdate=='NO' and $rightRead=='YES'))?'display:none':'').'" 
                  onclick="'.(($id!=0 and  $rightUpdate=='YES' )?"nextSlides('prev',".$id.",'".$refType."',".$refId.");":"").'">&#10094;</div>';
        echo ' </td>';
        echo ' <td style="width:76%;height:100%;'.$backgroundColor.'">';
          echo '<div  class="slideshow-container" style="width:100%;height:20px">';
          echo '<input id="'.$refType.'_'.$refId.'_pos_'.$id.'" value="'.$pos.'" type="hidden" />';
          
          echo '<div class="mySlides fade" style="'.(($done==0 && $idle==0 && $handled==0 && $paused==0)?'display:block;':'display:none;').';padding-top:1px;">';
          echo '  <div class="slideStatus">&nbsp;</div>';
          echo '</div>';

          echo '<div class="mySlides fade" style="'.(($paused==1)?'display:block;':'display:none;').';padding-top:1px;">';
          echo '  <div class="slideStatus"><span style="font-weight: bolder;">'.i18n('subTaskStatusOnHold').'</span></div>';
          echo '</div>';
          
          echo '<div class="mySlides fade" style="'.(($handled==1)?'display:block;':'display:none;').';padding-top:1px;">';
          echo '  <div class="slideStatus"><span  style="font-weight: bolder;">'.i18n('colHandled').'</span></div>';
          echo '</div>';
          
          echo '<div class="mySlides fade" style="'.(($done==1)?'display:block;':'display:none;').'padding-top:1px;">';
          echo '  <div class="slideStatus"><span  style="font-weight: bolder;">'.i18n('done').'</span></div>';
          echo '</div>';
          
           echo '<div class="mySlides fade" style="'.(($idle==1)?'display:block;':'display:none;').';padding-top:1px;">';
           echo   '<div class="slideStatus" ><span style="font-weight: bolder;">'.i18n('colIdle').'</span></div>';
           echo '</div>';

           echo '</div>';
         echo ' </td>';
         echo ' <td style="width:12%;height:100%;" >';
         echo '<div  id="'.$refType.'_'.$refId.'_next_'.$id.'" class="next todoList" style="'.(($id==0 or ($idle==1) or ($rightUpdate=="NO" and $rightRead=='YES'))?'display:none':'').'"  onclick="'.(($id!=0 and  $rightUpdate=='YES')?"nextSlides('next',".$id.",'".$refType."',".$refId.");":"").'">&#10095;</div>';
         echo ' </td>';
       echo '</tr>';
     echo '</table>';
     echo '</div>';
  }
  
  
  static function drawAllSubTask($idProject,$idResource,$elementType,$idVersion,$idPriority,$orderBy){
    $tab= array();
    $subTask= new SubTask();
    $ticket=new Ticket();
    $action=new Action();
    $activity=new Activity();
    $user=getSessionUser();
    
    $tableName=$subTask->getDatabaseTableName();
    $showClosedSubTask=(Parameter::getUserParameter('showClosedSubTask_Global')!='' and Parameter::getUserParameter('showClosedSubTask_Global')!='0')?true:false;
    $showDoneSubTask=((Parameter::getUserParameter('showDoneSubTask_Global')!='0') or $showClosedSubTask==true)?true:false;
    $query="SELECT DISTINCT  $tableName.refId as refid, $tableName.refType as reftype, $tableName.idProject as idproject FROM $tableName ";
    $query.="WHERE 1=1";
    if($idProject!=0){
      $lstProj=$idProject;
      $idProjects=pq_explode(',', $idProject);
      $idProjectsFlip=array_flip($idProjects);
      foreach ($idProjects as $id=>$idP){
        $proj=new Project($idP);
        $sub=$proj->getRecursiveSubProjectsFlatList();
        if(!empty($sub)){
          foreach ($sub as $id=>$subproj){
            if(pq_array_key_exists($id, $idProjectsFlip))continue;
            $lstProj.=",".$id;
          }
        }
      }
      $query.=" and  $tableName.idProject in (".$lstProj.")";
    }else {
      $visibleProject= transformListIntoInClause($user->getVisibleProjects());
      $query.=" and  $tableName.idProject in ".$visibleProject;
    }
    if(pq_trim($elementType)!=''){
      $query.=" and  $tableName.refType = '".$elementType."'";
    }

    if($idResource!=0){
      $query.=" and  $tableName.idResource = ".$idResource;
      if($showClosedSubTask!=1)$query.=" and  $tableName.idle = 0";
    }
    if ($idVersion!=0)$query.=" and  $tableName.idTargetProductVersion = ".$idVersion;
    if ($idPriority!=0)$query.=" and  $tableName.idPriority = ".$idPriority;
    $result=Sql::query($query);
    while ($line = Sql::fetchLine($result)) {
      $tab[]=$line;
    }
    $status=new Status();
    $priority=new Priority();
    $allPrio=$priority->getSqlElementsFromCriteria(null,null,"1=1");
    $allStatus=$status->getSqlElementsFromCriteria(null,null,"1=1");
    foreach ($allPrio as $id=>$priority){
      echo '<input id="colorPrio_'.$priority->id.'" value="'.$priority->color.'" type="hidden" />';
    }
    foreach ($allStatus as $id=>$status){
      echo '<input id="colorStatus_'.$status->id.'" value="'.$status->color.'" type="hidden" />';
    }
    echo      '<input id="subTaskView" value="Global" type="hidden" />';
    echo      '<input id="subTaskViewMaxFileSize" value="'.Parameter::getGlobalParameter('paramAttachmentMaxSize').'" type="hidden" />';
    echo      '<input id="refreshSTDivValues" value="" type="hidden" />';
    $drew=false;
    if(!empty($tab)){
      foreach ($tab as $id=>$obj){
        $showElemSubTask=true;
        $onlyHisSubTask=false;
        $element= new $obj['reftype']( $obj['refid']);
        $statusElment= new Status($element->idStatus);
        $colorStatus=$statusElment->color;
        //$menName= new Menu($element->idMenu);
        $rightUpdate=securityGetAccessRightYesNo('menu'.get_class($element),'update',$element);
        $rightRead=securityGetAccessRightYesNo('menu'.get_class($element),'read',$element);
        $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array('name'=>'menu'.get_class($element)));
        if (!Module::isMenuActive($menu->name))  $showElemSubTask=false;
        if (!securityCheckDisplayMenu($menu->id,pq_substr($menu->name,4)))$showElemSubTask=false;
        if(!$showElemSubTask){
          $critArray=array('idResource'=>$user->id,'reftype'=>get_class($element),'refid'=>$element->id);
          if(!$showClosedSubTask and !$showDoneSubTask  ){
            $critArray=array('idResource'=>$user->id,'reftype'=>get_class($element),'refid'=>$element->id,"done"=>'0',"idle"=>'0');
          }else if($showDoneSubTask and !$showClosedSubTask){
            $critArray=array('idResource'=>$user->id,'reftype'=>get_class($element),'refid'=>$element->id,"idle"=>'0');
          }
          $nbTodoListForUser=$subTask->countSqlElementsFromCriteria($critArray);
          if($nbTodoListForUser!=0){
            $rightUpdate='NO';
            $onlyHisSubTask=true;
          }
          else continue;

        }
        //if (($element->idle==1) or ($element->done==1) or ($rightUpdate=='NO' and $rightRead=='NO') or (!$rightUpdate and !$rightRead))continue;
        if (($element->idle==1) or ($rightUpdate=='NO' and $rightRead=='NO') or (!$rightUpdate and !$rightRead))continue; // Ticket #6914
        $where="refType= '".$obj['reftype']."' and refId = ".$element->id;
        $crit=array();
        if(!$showClosedSubTask and !$showDoneSubTask  ){
          $crit=array("done"=>'0',"idle"=>'0');
        }else if($showDoneSubTask and !$showClosedSubTask){
          $crit=array("idle"=>'0');
        }
        $cpST=$subTask->countSqlElementsFromCriteria(array_merge(array("refType"=>$obj['reftype'],"refId"=>$element->id),$crit));
        if ($cpST==0 )continue;
        $goto="";
        $style="";
        //$version=(property_exists(get_class($element), 'idTargetProductVersion') and $element->idTargetProductVersion!='')?new ProductVersion($element->idTargetProductVersion):'';
        if ( securityCheckDisplayMenu(null, get_class($element)) and $rightRead=="YES") {
          $goto=' onClick="gotoElement(\''.$obj['reftype'].'\',\''.htmlEncode($element->id).'\');" ';
          $style='cursor: pointer;';
        }
        
          echo '<table style="width:95%; margin-bottom:45px;">';
            echo '<tr style="height:42px;"><td colspan="4" ><div dojotype="dijit.layout.ContentPane" class="dijitContentPane" >';
              echo'<table style="width:100%;"><tr>';
                    echo '<td style="width:64%;">';
                      echo '<div class="reportHeader" style="width:100%;height:42px;border-radius:unset!important;"><span style="text-align:left;margin-left:25px;float:left;padding-top:12px;'.$style.'" class="classLinkName" '.$goto.'>'
                      //    .pq_ucfirst($obj['reftype']).'&nbsp#'.$element->id.'&nbsp-&nbsp'.$element->name.'&nbsp;'.((property_exists(get_class($element), 'idTargetProductVersion'))? '|&nbsp;'.pq_ucfirst(i18n('colVersion')).':&nbsp;'.(($element->idTargetProductVersion!='')?$version->name:$version):"").'</span></div>';
                      .i18n('Project')." #".$obj['idproject']." - " .SqlList::getNameFromId('Project', $obj['idproject'])." | ".i18n(pq_ucfirst($obj['reftype'])).'&nbsp#'.$element->id.'&nbsp-&nbsp'.$element->name.'</span></div>';
                    echo '</td>';
                    if(Module::isModuleActive('moduleConfiguration') and property_exists(get_class($element), 'idTargetProductVersion')){
                      echo '<td class="reportHeader" style="width:12%;">';
                      echo '<div  style="width:90%;height:42px;border-radius:unset!important;vertical-align:middle;">';
                      echo      '<select dojoType="dijit.form.FilteringSelect" id="idVersionElement_'.$obj['reftype'].'_'.$element->id.'" name="idVersionElement_'.$obj['reftype'].'_'.$element->id.'" '.(( $rightUpdate=='NO' and $rightRead=="YES")?'readonly="true"':'').'
                                    title="'.i18n("ProductVersion").'" 
                                    style="width:auto;margin-top:7px;" class="input" onChange="saveActivityValueFilter(\'Version\',\''.$obj['reftype'].'\','.$element->id.'); "  '.autoOpenFilteringSelect().'>';
                                htmlDrawOptionForReference('idTargetProductVersion',$element->idTargetProductVersion,$element);
                      echo      '</select>';
                      echo '</div>';
                      echo      '<input id="idOldVersionElement_'.$obj['reftype'].'_'.$element->id.'" value="'.$element->idTargetProductVersion.'" type="hidden" />';
                      echo '</td>';
                    }
                    echo '<td class="reportHeader" style="width:'.(property_exists(get_class($element), 'idTargetProductVersion')?'12%':'24').';">';
                      echo '<div  style="width:100%;height:42px;border-radius:unset!important;vertical-align:middle;">';
                         echo '<div id="status_'.$obj['reftype'].'_'.$element->id.'" style="width:90%;margin-left: 5%;margin-right: 5%;height:100%;background-color:'.$colorStatus.';">';
                          echo      '<select dojoType="dijit.form.FilteringSelect" id="idStatusElement_'.$obj['reftype'].'_'.$element->id.'" name="idStatusElement_'.$obj['reftype'].'_'.$element->id.'" '.(( $rightUpdate=='NO' and $rightRead=="YES")?'readonly="true"':'').'
                                    title="'.i18n("Status").'" 
                                    style="width:auto;margin-top:7px;" class="input" onChange="saveActivityValueFilter(\'Status\',\''.$obj['reftype'].'\','.$element->id.'); "  '.autoOpenFilteringSelect().'>';
                            htmlDrawOptionForReference('idStatus',$element->idStatus,$element);
                          echo      '</select>';
                         echo '</div>';
                       echo '';
                       echo      '<input id="idOldStatusElement_'.$obj['reftype'].'_'.$element->id.'" value="'.$element->idStatus.'" type="hidden" />';
                    echo '</td>';
                    echo '<td class="reportHeader" style="width:'.(property_exists(get_class($element), 'idTargetProductVersion')?'12%':'24').';">';
                       echo '<div style="width:90%;height:42px;border-radius:unset!important;vertical-align:middle;">';
                        echo      '<select dojoType="dijit.form.FilteringSelect" id="idResourceElement_'.$obj['reftype'].'_'.$element->id.'" name="idResourceElement_'.$obj['reftype'].'_'.$element->id.'" '.(( $rightUpdate=='NO' and $rightRead=="YES")?'readonly="true"':'').'
                                    title="'.i18n("Responsible").'" 
                            style="width:auto;margin-top:7px;" class="input" onChange="saveActivityValueFilter(\'Resposible\',\''.$obj['reftype'].'\','.$element->id.');" '.autoOpenFilteringSelect().' >';
                          htmlDrawOptionForReference('idResource',$element->idResource,$element);
                        echo      '</select>';
                       echo '</div>';
                       echo      '<input id="idOldResourceElement_'.$obj['reftype'].'_'.$element->id.'" value="'.$element->idResource.'" type="hidden" />';
                     echo '</td >';
              echo'</tr></table>';
            echo '</div></td></tr>';
            SubTask::drawSubtasksForObject($element, $obj['reftype'],  $obj['refid'],$rightUpdate,$rightRead,null,$idResource,true,false,$onlyHisSubTask,$idPriority,$orderBy);
          echo '</table>';
          if(!$drew){
            $drew=true;
          }
      }
      if (!$drew){
        echo '<table style="width:95%; margin-bottom:10px;">';
        echo '   <tr>';
        echo '    <td colspan="10">';
        echo '    <div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;width:100%;border-right: 1px solid grey;">'.i18n('noDataFound').'</div>';
        echo '    </td>';
        echo '   </tr>';
        echo '</table>';
      }
    }else{
      echo '<table style="width:95%; margin-bottom:10px;">';
  	  echo '   <tr>';
      echo '    <td colspan="10">';
      echo '    <div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;width:100%;border-right: 1px solid grey;">'.i18n('noDataFound').'</div>';
      echo '    </td>';
      echo '   </tr>';
      echo '</table>';
    }
  }
  
  // ============================================================================**********
  // CONTROL
  // ============================================================================**********
  public function control(){
    $result="";
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }

  // ============================================================================**********
  // SAVE
  // ============================================================================**********
  public function save() {
    if (!empty($this->name)) {
      $this->name = html_entity_decode($this->name, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    }
    $result=parent::save();
    return $result;
  }
  
  
}
?>
