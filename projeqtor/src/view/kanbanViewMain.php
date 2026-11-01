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

$searchByName = Parameter::getUserParameter('kanbanSearchByName');
$searchByResponsible = Parameter::getUserParameter('kanbanSearchByResponsible');
$searchByStatus = Parameter::getUserParameter('kanbanSearchByStatus');
$searchByTargetProductVersion = Parameter::getUserParameter('kanbanSearchByTargetProductVersion');
$orderBy = Parameter::getUserParameter('kanbanOrderBy');

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
$typeKanbanC="Ticket";
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
$user = getSessionUser();
$arrayProject=array();
$hasVersion=(property_exists($typeKanbanC,'idTargetProductVersion'))?true:false;

if($typeKanbanC != 'Activity' and $orderBy == 'validatedenddate')$orderBy="";
?>
<div class="container" dojoType="dijit.layout.BorderContainer" id="divKanbanAllContainer">
  <div id="titleKanban" class="listTitle" style="z-index:3;overflow:visible;min-height:65px;"
    dojoType="dijit.layout.ContentPane" region="top">
    <table width="100%">
      <tr height="100%" style="vertical-align: middle;">
        <td align="center" style="width:50px;">          
          <div style="position:absolute;top:2px">
            <?php echo formatIcon('Kanban',32,null,true);?>
          </div>
        </td>
        <td class="title" style="height:35px;width:100px;">    
          <div style="width:100%;height:100%;position:relative;">
            <div id="menuName" style="float:left;width:100%;position:absolute;top:8px;text-overflow:ellipsis;overflow:hidden;">
              <?php if (isNewGui()) {?>           
              <span id="gridRowCountShadow1" style="display:none;" class=""></span>
              <span id="gridRowCountShadow2" style="display:none;" class=""></span>
              <span id="gridRowCount" style="padding-left:5px" class=""></span>
              <?php }?> 
              <span id="classNameSpan" style="">
              <?php echo i18n('kanbanTitleButton');?>
              </span>
            </div>
          </div>
        </td>
        <td style="width:32px;">
         <?php if($idKanban==-1){ ?>
          <div style="float:left">
            <div dojoType="dijit.form.Button" class="detailButton" onclick="loadDialog('dialogKanbanUpdate', function(){kanbanFindTitle('addKanban');}, true, '&typeDynamic=addKanban', true, false);"
            style="float:left;position:relative;margin-right:8px;"><?php echo formatIcon('KanbanAdd',22,i18n('kanbanAdd')); ?>
            </div>
          </div>
          <?php } ?>
        </td>
        <td style="width:75px;"><?php echo i18n('labelKanbanList');?> : </td>
        <td><?php kanbanListSelect($user,$name,$type,$idKanban);?></td>
      </tr>
    </table>
    <input type="hidden" name="objectClassManual" id="objectClassManual" value="Kanban" />
    <input type="hidden" id="objectClassList" name="objectClassList" value="<?php echo $typeKanbanC;?>">
    <input type="hidden" name="idKanban" id="idKanban" value="<?php echo $idKanban;?>" />
    <input type="hidden" name="typeKanban" id="typeKanban" value="<?php echo $type;?>" />
    <input type="hidden" id="classKanban" name="classKanban" value="<?php echo $typeKanbanC;?>">
    <input dojoType="dijit.form.TextBox" type="hidden" id="refreshActionAddItemKanban" value="-1" onchange="refreshActionAddItemKanban(this);">
    <div style="width:100%; margin: 0px 10px 3px 10px" dojoType="dijit.layout.ContentPane" region="bottom">
      <?php if($idKanban!=-1){?>
      <?php echo i18n("colName");?> : <input dojoType="dijit.form.TextBox" onKeyUp="filterKanban();saveDataToSession('kanbanSearchByName', dojo.byId('searchByName').value, true);" class="dijit dijitReset dijitInline dijitLeft filterField rounded dijitTextBox" type="text" id="searchByName" value="<?php echo $searchByName;?>">
      <?php echo i18n("colResponsible");?> : 
      <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
        <?php echo autoOpenFilteringSelect ();?>
        style="width: 150px;" onChange="filterKanban();saveDataToSession('kanbanSearchByResponsible', this.value, true);" name="searchByResponsible" id="searchByResponsible"
        value="<?php echo $searchByResponsible;?>">
          <option value=""></option>
            <?php $specific='diary';
              include '../tool/drawResourceListForSpecificAccess.php';?> 
      </select>
  		<?php if($type!='Status'){echo i18n("colIdStatus");?> : 
    	<select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 150px;" 
        <?php echo autoOpenFilteringSelect ();?>
    		onChange="filterKanban();saveDataToSession('kanbanSearchByStatus', this.value, true);" name="searchByStatus" id="searchByStatus" value="<?php echo $searchByStatus?>" >
      	<?php htmlDrawOptionForReference("idStatus", null);?>
    	</select>
  		<?php } if($type!='TargetProductVersion' and $hasVersion){echo i18n("colIdVersion"); ?> : 
      <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 150px;" 
      <?php echo autoOpenFilteringSelect ();?>
      onChange="filterKanban();saveDataToSession('kanbanSearchByTargetProductVersion', this.value, true);" name="searchByTargetProductVersion" id="searchByTargetProductVersion" 
      value="<?php echo $searchByTargetProductVersion;?>">
        <?php if(is_numeric(getSessionValue("project"))){
          htmlDrawOptionForReference("idTargetProductVersion", null, null, false, 'idProject', getSessionValue("project"));
        }else{
          htmlDrawOptionForReference("idTargetProductVersion", null);
        }?>
      </select>
      <?php } echo i18n("sortedBy"); ?> : 
      <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;margin-right:15px;"
      <?php echo autoOpenFilteringSelect ();?>
      onChange="saveDataToSession('kanbanOrderBy', this.value, true);filterKanban(true);" name="kanbanOrderBy" id="kanbanOrderBy">
        <option <?php if($orderBy=="")echo "selected";?> value=""></option>
        <option <?php if($orderBy=="name")echo "selected";?> value="name"><?php echo i18n("colName");?></option>
        <option <?php if($orderBy=="idresponsible")echo "selected";?> value="idresponsible"><?php echo i18n("colResponsible");?></option>
        <option <?php if($orderBy=="idstatus")echo "selected";?> value="idstatus"><?php echo i18n("colIdStatus");?></option>
        <?php if ($hasVersion) {?><option <?php if($orderBy=="idtargetproductversion")echo "selected";?> value="idtargetproductversion"><?php echo i18n("colIdTargetProductVersion");?></option><?php }?>
        <?php if ($typeKanbanC == 'Activity') {?><option <?php if($orderBy=="validatedenddate")echo "selected";?> value="validatedenddate"><?php echo i18n("colValidatedEndDate");?></option><?php }?>
        <option <?php if($orderBy=="idpriority")echo "selected";?> value="idpriority"><?php echo i18n("colIdPriority");?></option>
        <option <?php if($orderBy=="id")echo "selected";?> value="id"><?php echo i18n("colId");?></option>
      </select>
      <button title="<?php echo i18n('advancedFilter')?>" class="comboButton" dojoType="dijit.form.DropDownButton" id="listFilterFilter" 
        name="listFilterFilter" style="margin-right:15px;"
        iconClass="dijitButtonIcon icon<?php echo (isset(getSessionUser()->_arrayFilters[$typeKanbanC]) && is_array(getSessionUser()->_arrayFilters[$typeKanbanC]) && count(getSessionUser()->_arrayFilters[$typeKanbanC])!=0 ? 'Active' : '');?>Filter" showLabel="false">
           <?php if (!isNewGui()){ ?>
            <script type="dojo/connect" event="onClick" args="evt">
            showFilterDialog();
          </script>
            <script type="dojo/method" event="onMouseEnter" args="evt">
            clearTimeout(closeFilterListTimeout);
            clearTimeout(openFilterListTimeout);
            openFilterListTimeout=setTimeout("dijit.byId('listFilterFilter').openDropDown();",popupOpenDelay);
          </script>
            <script type="dojo/method" event="onMouseLeave" args="evt">
            clearTimeout(openFilterListTimeout);
            closeFilterListTimeout=setTimeout("dijit.byId('listFilterFilter').closeDropDown();",2000);
          </script>
         <?php }?>
          <div dojoType="dijit.TooltipDialog" id="directFilterList" style="z-index: 999999;display:none; position: absolute;">
            <?php 
              //$_REQUEST['filterObjectClass']=$objectClass;
              //$_REQUEST['context']="directFilterList";
              $_REQUEST['context']='directFilterList';
              $_REQUEST['contentLoad']="../tool/jsonKanban.php";
              $_REQUEST['container']="kanbanJsonData";
              $_REQUEST['filterObjectClass']=$typeKanbanC;
              if(isNewGui()){
                $filterObjectClass = $typeKanbanC;
                $dontDisplay = true;
                include "../tool/displayQuickFilterList.php";
              }
              //ajout de mehdi
              include "../tool/displayFilterList.php";
            ?>
           <?php if (!isNewGui()){ ?>
              <script type="dojo/method" event="onMouseEnter" args="evt">
                clearTimeout(closeFilterListTimeout);
                clearTimeout(openFilterListTimeout);
              </script>
              <script type="dojo/method" event="onMouseLeave" args="evt">
                dijit.byId('listFilterFilter').closeDropDown();
              </script>
           <?php }?>
          </div> 
      </button>
      <?php }?>
      <div style="float:right;padding-right:1%;">
          <?php if($idKanban!=-1){ ?>
          <div dojoType="dijit.form.DropDownButton"							    
           id="extraButtonKanban" jsId="extraButtonKanban" name="extraButtonKanban" 
           showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton" 
           title="<?php echo i18n('extraButtons');?>">
             <div dojoType="dijit.TooltipDialog" class="white" id="extraButtonKanbanDialog" tyle="position: absolute; top: 50px; right: 40%">        
               <table style="margin:5px">
                 <tr style="width:100%;">
                  <td><?php kanbanParameterList($idKanban);?></td>
                 </tr>
               </table>
             </div>
          </div>
          <?php }?>
          <?php if($idKanban!=-1){?>
          <div dojoType="dijit.form.Button" class="detailButton" style="float:left; position:relative; cursor:pointer; margin-right:10px; margin-top:5px;"
            onclick="addItemFromKanban('<?php echo $typeKanbanC;?>');"><?php echo formatIcon('KanbanAdd'.$typeKanbanC,22, i18n('kanbanAdd'.$typeKanbanC)); ?>
          </div>
          <?php }?>
      </div>
    </div>
    <div dojoType="dijit.layout.ContentPane" id="kanbanJsonData" jsId="kanbanJsonData" style="display:none">
    <?php include '../tool/jsonKanban.php';?>
  	</div>
  </div>
  <div class="container" dojoType="dijit.layout.ContentPane" id="divKanbanContainer" region="center" style=" overflow-x:scroll;">
    <?php include "../view/kanbanView.php";?>
  </div>
</div>
<?php 
if (pq_array_key_exists ( 'storeParameterBottomLiveMeeting', $_REQUEST )) {
  Parameter::storeUserParameter('storeParameterBottomLiveMeeting', 'kanban');
}
?>