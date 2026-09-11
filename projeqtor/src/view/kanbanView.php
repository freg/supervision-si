<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
require_once "../tool/kanbanConstructPrinc.php";
require_once '../tool/kanbanFunction.php';
global $typeKanbanC;
global $orderBy;
$orderBy="";
if(pq_array_key_exists('kanbanOrderBy',$_REQUEST)){
  $orderBy=$_REQUEST['kanbanOrderBy'];
  setSessionValue('kanbanOrderBy', $orderBy);
}else if(sessionValueExists('kanbanOrderBy')){
  $orderBy=getSessionValue('kanbanOrderBy');
}
$typeKanbanC="Ticket";
$seeWork=Parameter::getUserParameter("kanbanSeeWork");
$seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
if(PlanningElement::getWorkVisibiliy(getSessionUser()->idProfile) != "ALL")$seeWork=false;
if(Parameter::getUserParameter("kanbanShowIdle")==null){
  Parameter::storeUserParameter("kanbanShowIdle", 'off');
}
$idKanban=-1;
if (pq_array_key_exists('idKanban',$_REQUEST)) {
  $idKanban=$_REQUEST['idKanban'];
  if (is_numeric($idKanban)) Parameter::storeUserParameter("kanbanIdKanban",$idKanban);
}else{
  if(Parameter::getUserParameter("kanbanIdKanban")!==null){
    $idKanban=Parameter::getUserParameter("kanbanIdKanban");
  }
}
$kanTest=new Kanban($idKanban,true);
if($kanTest->name=='')$idKanban=-1;
$json="";
$type="";
$name="";
if($idKanban!=-1){
  $kanB=new Kanban($idKanban,true);
  $json=$kanB->param;
  $type=$kanB->type;
  $name=$kanB->name;
  $jsonDecode=json_decode($json,true);
  if(!isset($jsonDecode['typeData'])){
    $jsonDecode['typeData']='Ticket';
    $kanB->param=json_encode($jsonDecode);
    $kanB->save();
  }
  $typeKanbanC=$jsonDecode['typeData'];
}

$arrayProject=array();
$hasVersion=(property_exists($typeKanbanC,'idTargetProductVersion'))?true:false;

if($typeKanbanC != 'Activity' and $orderBy == 'validatedenddate')$orderBy="";

?>
<div id="kanbanContainer" style="height:100%;padding:16px 8px 8px 8px;" onscroll="kanbanScrollTop=this.scrollTop">
    <table width="100%" style="min-height:100%;">
      <tr>
        <?php if($idKanban!=-1)drawColumnKanban($type,$jsonDecode,$idKanban); ?>
      </tr>
    </table>
    <div class="contextMenuClass comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="kanbanContextMenu" name="kanbanContextMenu" style="position:absolute;top:0px;left:0px;width:0px;height:0px;overflow:hidden;">
      <div dojoType="dijit.TooltipDialog" id="dialogKanbanContextMenu" tabindex="0"" onMouseEnter="clearTimeout(hideKanbanContextMenuTimeout);" onMouseLeave="hideKanbanContextMenu(200)" onfocusout="hideElementOnFocusOut(null, hideKanban(200))">
        <input type="hidden" id="contextMenuRefId" name="contextMenuRefId" value="" />
      	<input type="hidden" id="contextMenuRefType" name="contextMenuRefType" value="" />
        <input type="hidden" id="objectClass" name="objectClass" value="<?php echo $typeKanbanC; ?>" />
        <input type="hidden" id="objectId" name="objectId" value="" />
        <input type="hidden" id="objectClassRow" name="objectClassRow" value="" />
        <input type="hidden" id="objectIdRow" name="objectIdRow" value="" />
        <table style="width:100%;height:100%">
          <tr id='addFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Add', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='addFromKanban_label'><?php echo i18n('contextMenuButtonNew');?></td>
          </tr>
          <tr id='editFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Edit', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='editFromKanban_label'><?php echo i18n('contextMenuButtonEdit');?></td>
          </tr>
          <tr id='copyFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Copy', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='copyFromKanban_label'><?php echo i18n('contextMenuButtonCopy');?></td>
          </tr>
          <tr id='addCommentFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('AddComment', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='addCommentFromKanban_label'><?php echo i18n('commentImputationAdd');?></td>
          </tr>
          <tr id='removeFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Remove', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='removeFromKanban_label'><?php echo i18n('contextMenuButtonDelete');?></td>
          </tr>
          <tr id='printFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Print', true , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='printFromKanban_label'><?php echo i18n('contextMenuButtonPrint');?></td>
          </tr>
          <tr id='printPdfFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Pdf', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='printPdfFromKanban_label'><?php echo i18n('reportPrintPdf');?></td>
          </tr>
          <tr id='mailFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Email', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='mailFromKanban_label'><?php echo i18n('contextMenuButtonMail');?></td>
          </tr>
          <?php if($typeKanbanC=="Activity"){ ?>
          <tr id='searchFromKanban' class='contextMenuRow' onClick=''>
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('SearchPlanning', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='searchFromKanban_label'><?php echo i18n('buttonSearch');?></td>
          </tr>
          <?php } ?>
        </table>
      </div>
    </div>
  </div>