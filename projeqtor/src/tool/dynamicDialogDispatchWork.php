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
require_once "../tool/projeqtor.php";
if (! pq_array_key_exists('refType',$_REQUEST)) {
 throwError('Parameter refType not found in REQUEST');
}
$objectClass=$_REQUEST['refType'];
Security::checkValidClass($objectClass);

if (! pq_array_key_exists('refId',$_REQUEST)) {
 throwError('Parameter refId not found in REQUEST');
}

$objectId=$_REQUEST['refId'];
$obj=new $objectClass($objectId); // Note: $objectId is checked in base SqlElement constructor to be numeric value.
$crit=array('refType'=>$objectClass,'refId'=>$objectId);
$we=SqlElement::getSingleSqlElementFromCriteria('WorkElement', $crit);
if (!$we->id) {
  // This is possible only if some duplicate WorkElement exists : delete one and keep only the other
  $lstWe=$we->getSqlElementsFromCriteria($crit,false,null,'id asc');
  $we=null;
  foreach ($lstWe as $weTmp) {
    if (!$we) {
      $we=$weTmp;
      continue;
    } else {
      traceLog("WARNING : purge duplicate workelement #".$weTmp->id." for ".$objectClass." #".$objectId);
      $weTmp->delete();
    }
  }
}
if ($we->refType) {
  $refObj = new $we->refType ( $we->refId );
} else {
  $refObj = new Ticket();
}
$canUpdate = (securityGetAccessRightYesNo ( 'menu' . $we->refType, 'update', $refObj ) == 'YES');
$we->setAttributes();
if ($we->isAttributeSetToField('realWork', 'readonly') or $we->isAttributeSetToField('realWork', 'hidden')) {
  $canUpdate=false;
}
$arrayWork=array();
$crit=array('idWorkElement'=>$we->id);
$w=new Work();
$list=$w->getSqlElementsFromCriteria($crit);
$totalWork=0;
$critIdWorkList='0';
foreach ($list as $w) {
  $key=$w->day.'#'.$w->idResource;
  if (! isset($arrayWork[$key])) {
    $arrayWork[$key]=array('id'=>$w->id, 'date'=>$w->workDate, 'idResource'=>$w->idResource,'work'=>0);
    $critIdWorkList.=','.$w->id;
  } else {
    // duplicate exist : fix = merge the two work items
    $merged=new Work($arrayWork[$key]['id']);
    $merged->work+=$w->work;
    $merged->save();
    $w->delete();
  }
  $arrayWork[$key]['work']+=$w->work;
  $totalWork+=$w->work;
}
//gautier #6991
ksort($arrayWork);
$key=date('Ymd').'#'.getSessionUser()->id;
if (! isset($arrayWork[$key])) { 
  $arrayWork[$key]=array('id'=>'', 'date'=>date('Y-m-d'), 'idResource'=>getSessionUser()->id,'work'=>0);
}
if (isset($_REQUEST['work'])) {
  $newWork=Work::convertImputation($_REQUEST['work']); // Note: implicit conversion to numeric value do to arithmetic operation
  if (round($newWork,3)>round($totalWork,3)) { $arrayWork[$key]['work']=$newWork-$totalWork;}
}
$arrayWork[]=array('id'=>'', 'date'=>null, 'idResource'=>null,'work'=>0);
$keyDownEventScript=NumberFormatter52::getKeyDownEvent(); 

$activeToken=false;
$leftToken=false;
$usedToken=false;
if(Module::isModuleActive('moduleTokenManagement') ){
  $totalQuantity=0;
  $totalQuantityMarkup=0;
  $idProj=$we->idProject;
  $lstTokenCC=array();
  $lstTokenDefSplittable=array();
  $lstMaxDurationLeftToken=array();
  $clientContract= new ClientContract();
  $workToken= new TokenDefinition();
  $workTokenCC= new WorkTokenClientContract();
  $workTokenCCWork= new WorkTokenClientContractWork();
  
  $tableCC=$clientContract->getDatabaseTableName();
  $workTokenTable= $workToken->getDatabaseTableName();
  
  //$queryLstCC="(SELECT DISTINCT tcc.id as id FROM $tableCC as tcc WHERE tcc.idProject=$idProj )";//and tcc.idle = 0
  $proj=new Project($idProj, true);
  $listProj=transformValueListIntoInClause($proj->getTopProjectList(true));
  $queryLstCC="(SELECT DISTINCT tcc.id as id FROM $tableCC as tcc WHERE tcc.idProject in $listProj )";
  $where=" idClientContract in $queryLstCC";
  $lstTokenCC=$workTokenCC->getSqlElementsFromCriteria(null,false,$where);
  $where .=" and idWorkToken in (SELECT DISTINCT wt.id FROM $workTokenTable as wt WHERE wt.splittable=1)";
  $lstWTCCSplitable=$workTokenCC->getSqlElementsFromCriteria(null,false,$where);
  if(!empty($lstTokenCC)){
    $activeToken=true;
    foreach ($lstTokenCC as $id=>$wCC){
      if ($wCC->fullyConsumed!=1) $leftToken=true;
      $sumWorkCCW=$workTokenCCWork->sumSqlElementsFromCriteria('workTokenQuantity', array('idWorkTokenClientContract'=>$wCC->id,'billable'=>1));
      $leftDuration=$wCC->quantity-$sumWorkCCW;
      if(isset($lstMaxDurationLeftToken["idWT_".$wCC->idWorkToken]))$lstMaxDurationLeftToken["idWT_".$wCC->idWorkToken]+=$leftDuration;
      else $lstMaxDurationLeftToken["idWT_".$wCC->idWorkToken]=$leftDuration;
    
    }
    foreach ($lstWTCCSplitable as $wtcc){
      $lstTokenDefSplittable[$wtcc->id]=$wtcc->id;
    }
    $workTokenWork=$workTokenCCWork->countSqlElementsFromCriteria(null,"idWork in ($critIdWorkList)");
    if ($workTokenWork>0) $usedToken=true;
    if ($usedToken==false and $leftToken==false) $activeToken=false;
  }else{
    $activeToken=false;
  }
}
$globalHeight=RequestHandler::getValue("heightWindow");
$divHeight=$globalHeight*0.6;
?>
<form dojoType="dijit.form.Form" id="dialogDispatchWorkForm" name="dialogDispatchWorkForm" action="">
<table style="<?php echo ($activeToken)?'width:1035px;':'width:100%;'?>">
<thead>
<tr><td class="tabLabel" style="<?php echo ($activeToken)?'width:110px;':'width:100px;';?>"><?php echo i18n('colDate');?></td><td>&nbsp;</td>
    <?php if($activeToken) echo '<td class="tabLabel" style="width:74px;">'.i18n('colStartTime').'<div style="width:74px;text-align:center;position:absolute;font-size:75%;font-weight:normal;">'.i18n('localTime').'</div></td><td>&nbsp;</td>';?>
    <td class="tabLabel" style="<?php echo ($activeToken)?'width:150px;':'width:150px;';?>"><?php echo i18n('colResource');?></td><td>&nbsp;</td>
    <?php if ($canUpdate) {?> <td class="tabLabel" colspan="2" style="<?php echo ($activeToken)?'width:80px;':'width:60px;';?>"><?php echo i18n('colWork');?></td><td>&nbsp;</td><?php }?>
    <?php if($activeToken){
      echo '<td class="tabLabel" style="width:150px;">'.i18n("workTokenOrder").'</td><td>&nbsp;</td>';
      echo '<td class="tabLabel" style="width:160px;">'.i18n("colMarkupType").'</td><td>&nbsp;</td>';
      echo '<td class="tabLabel" style="width:62px;">'.lcfirst(i18n("quantity")).'</td><td>&nbsp;</td>';
      echo '<td class="tabLabel" style="width:62px;">'.i18n("quantityMarkup").'</td><td>&nbsp;</td>';
      echo '<td class="tabLabel" style="width:33px;">'.i18n("colBillable").'</td>';
    }?>
</tr>
</thead>
</table>
<div class="container"  style="max-height:<?php echo $divHeight; ?>px;;overflow-y:auto;margin:unset;">
<table style="<?php echo ($activeToken)?'width:995px;':'width:100%;'?>">
<input type="hidden" name="dispatchWorkObjectClass" value="<?php echo $objectClass;?>" />
<input type="hidden" name="dispatchWorkObjectId" value="<?php echo $objectId;?>" />
<input type="hidden" name="dispatchWorkElementId" value="<?php echo $we->id;?>" />

<tbody id="dialogDispatchTable">
<tr><td colspan="6">&nbsp;</td></tr>
<?php $total=0;$cpt=0;
$user=getSessionUser();
$crit=array('scope'=>'imputation', 'idProfile'=>$user->getProfile($obj));
$habilitation=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
$scope=new AccessScope($habilitation->rightAccess);
$code=$scope->accessCode;
$today=date('Y-m-d');
$nbFutureDays=Parameter::getGlobalParameter('maxDaysToBookWork');
if($nbFutureDays==null || $nbFutureDays=='')$nbFutureDays=-1;
$nbFutureDaysBlocking=Parameter::getGlobalParameter('maxDaysToBookWorkBlocking');
if($nbFutureDaysBlocking==null || $nbFutureDaysBlocking=='')$nbFutureDaysBlocking=-1;
$maxDateFuture=pq_strtotime("+".$nbFutureDays." days", pq_strtotime($today));
$maxDateFutureBlocking=pq_strtotime("+".$nbFutureDaysBlocking." days", pq_strtotime($today));
$listProject=Project::getAdminitrativeProjectList(true);
echo '<input type="hidden" id="nbFutureDays" value="'.$nbFutureDays.'" />';
echo '<input type="hidden" id="nbFutureDaysTime" value="'.$maxDateFuture.'" />';
echo '<input type="hidden" id="nbFutureDaysBlocking" value="'.$nbFutureDaysBlocking.'" />';
echo '<input type="hidden" id="nbFutureDaysBlockingTime" value="'.$maxDateFutureBlocking.'" />';
echo '<input type="hidden" id="isAdministrative" value="'.(pq_array_key_exists($we->idProject, $listProject) ? 1 : 0).'" />';
if($activeToken){
echo '<input type="hidden" id="moduleTokenActive" value="1" />';
echo '<input type="hidden" id="idProjectToken" value="'.$idProj.'" />';
echo '<input type="hidden" id="lstMaxDurationLeftToken" value="'.json_encode($lstMaxDurationLeftToken).'" />';
echo '<input type="hidden" id="lstTokenDefSplittable" value="'.implode(",", $lstTokenDefSplittable).'" />';
}

foreach($arrayWork as $key=>$work) {
  if (!$canUpdate and !$key) continue; 
  $cpt++;
  $selection=false;
  $readOnly=false;
  $hasWork=false;
  if($activeToken){
    $hasWork=false;
    $isplit=false;
    if ($work['id']!=""){
      $hasWork=true;
    }
    $tabTokenCC=$lstTokenCC;
  }
  if ($code!='PRO' and $code!='ALL' and $work['idResource'] and $work['idResource']!=$user->id) {
    $readOnly=true;
  }
  if (!$canUpdate) $readOnly=true;
  if($activeToken){
    if($hasWork){
      $workTokenWork=SqlElement::getSingleSqlElementFromCriteria('WorkTokenClientContractWork',array("idWork"=>$work['id']));
      if($workTokenWork->id){
         $selection=true;
         $workTokenMarkup=new WorkTokenMarkup();
         $workTokenClientContract=new WorkTokenClientContract($workTokenWork->idWorkTokenClientContract);
         $time=$workTokenWork->time;
         $lstWorkTokenMarkup=$workTokenMarkup->getSqlElementsFromCriteria(array("idWorkToken"=>$workTokenClientContract->idWorkToken));
         if(array_search($workTokenClientContract, $tabTokenCC)===false){
           array_push($tabTokenCC, $workTokenClientContract);
         }
         if(isset($lstTokenDefSplittable[$workTokenWork->idWorkTokenClientContract]))$isplit=true;
      }
    }
  }
  if (!$canUpdate and !$selection) continue;
  ?>
<tr>
 <td>
 <input type="hidden" name="dispatchWorkId[]" value="<?php echo $work['id'];?>" />
 <div id="dispatchWorkDate_<?php echo $cpt;?>" name="dispatchWorkDate[]"
           dojoType="dijit.form.DateTextBox" invalidMessage="<?php echo i18n('messageInvalidDate');?> " 
           <?php if ($readOnly) echo 'readonly';?>
           type="text" maxlength="10" style="width:100px; text-align: center;" class="input"
           hasDownArrow="true" constraints="{datePattern:browserLocaleDateFormatJs}"
           value="<?php echo $work['date']?>"></div>
 </td>
 <td>&nbsp;</td>
 <?php if($activeToken){
   ?>
   <td>
    <div id="tokenTime_<?php echo $cpt;?>" name="tokenTime[]"
           dojoType="dijit.form.TimeTextBox" invalidMessage="<?php echo i18n('messageInvalidTime');?> " 
           <?php if ($readOnly) echo 'readonly';?>
           type="text" maxlength="10" style="width:65px; text-align: center;" class="input"
           value="T<?php echo ($selection)?date('H:i',$time):(($work['date'])?date('H:i'):"");?>">
    </div>
  </td>
  <td>&nbsp;</td>
 <?php }?>
 <td><select dojoType="dijit.form.FilteringSelect" class="input" style="width:150px;" <?php if ($readOnly) echo 'readonly';?>
      id="dispatchWorkResource_<?php echo $cpt;?>" name="dispatchWorkResource[]" onMouseDown="dijit.byId(this.id).toggleDropDown();" selectOnClick="true">
     <?php 
     if ($code=="PRO" or $code=="ALL") {
        htmlDrawOptionForReference('idResource', $work['idResource'], $obj, false, 'idProject', $obj->idProject);
     } else {
       if ($readOnly) {
         echo '<option value="'.htmlEncode($work['idResource']).'">'.SqlList::getNameFromId('User', $work['idResource']).'</option>';
       } else {
         echo '<option value="'.htmlEncode($user->id).'">'.SqlList::getNameFromId('User', $user->id).'</option>';
       }    
     }?>
     </select>
 </td>
 <td>&nbsp;</td>
 <?php if ($canUpdate) {?>
 <td style="word-space:nowrap;width:52px">
   <div dojoType="dijit.form.NumberTextBox" class="input" style="width:50px;" value="<?php echo Work::displayImputation($work['work']);?>"
    onchange="updateDispatchWorkTotal('dispatchWorkValue_','dispatchWorkTotal');" name="dispatchWorkValue[]" 
    <?php if ($readOnly) echo 'readonly';?>
    id="dispatchWorkValue_<?php echo $cpt;?>">
    <?php echo $keyDownEventScript;?>  
         <?php 
      if($activeToken){
     ?>
     <script type="dojo/connect" event="onChange" args="evt">
      changeValueWorkTokenElement(<?php echo $cpt;?>);
     </script>
     <?php }?>
     </div>
 </td>
 <td style="width:1px;text-align:left;">&nbsp;<?php echo Work::displayShortImputationUnit();?></td>
 <td>&nbsp;</td>
 <?php }?>
  <?php if($activeToken) {
  if ($wCC->idleToken!=0) $readOnly=true;
 ?>
  <td>
    <select dojoType="dijit.form.FilteringSelect" class="input" style="width:150px;"  onMouseDown="dijit.byId(this.id).toggleDropDown();" selectOnClick="true"
      <?php if ($readOnly or !$hasWork) echo 'readonly';?>
      id="tokenType_<?php echo $cpt;?>" name="tokenType[]"  onchange="dispatchSetTokenTypeEvents(<?php echo $cpt;?>);">
      <?php 
      
        echo '<option value="" ></option>';
        foreach ($tabTokenCC as $id=>$val){
          $tokenName=SqlList::getNameFromId('TokenDefinition', $val->idWorkToken);
          $description=$val->description;
          $pos=pq_strpos(nl2br(pq_nvl($description)), '<br />');
          if($pos!==false){
            $descriptionTrun=pq_substr($description,0,$pos);
            $name=(pq_substr($descriptionTrun,0, 30)!='')?$tokenName.' - '.pq_substr($descriptionTrun,0, 30):$tokenName;
            
          }else{
            $name=(pq_substr($description,0, 30)!='')?$tokenName.' - '.pq_substr($description,0, 30):$tokenName;
          }
          if ( ($val->fullyConsumed!=1 and $val->idleToken==0) or ($selection and $val->id==$workTokenWork->idWorkTokenClientContract)) {
            echo '<option value="'. $val->id.'" '.(($selection and $val->id==$workTokenWork->idWorkTokenClientContract)?"selected":"").'>'.$name.'</option>';
          }
        }
      ?>
     </select>
  </td>
  <td>&nbsp;</td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input" style="width:150px;"  onMouseDown="dijit.byId(this.id).toggleDropDown();" selectOnClick="true"
      <?php if ($readOnly or !$hasWork) echo 'readonly';?>
      id="tokenMarkupType_<?php echo $cpt;?>" name="tokenMarkupType[]"  onchange="dispatchTokenMarkupTypeEvents(<?php echo $cpt;?>)">
      <?php 
      echo '<option value="" ></option>';
      if($selection){
        foreach ($lstWorkTokenMarkup as $id=>$val){
          echo '<option value="'. $val->id.'_'.$val->coefficient.'" '.(($val->id==$workTokenWork->idWorkTokenMarkup)?"selected":"").'>'.$val->name.'</option>';
        }
      }
      ?>
     </select>
  </td>
  <td>&nbsp;</td>
    <?php 
    $quantity=($selection)?$workTokenWork->workTokenQuantity:"";
    $totalQuantity+=($quantity!="")?$quantity:0;
  ?>
  <td style="text-align:center">
    <div dojoType="dijit.form.NumberTextBox" class="input" style="width:50px;" value="<?php echo $quantity; ?>"
      name="tokenQuantityValue[]"    data-dojo-props = "<?php echo ($isplit)?"constraints :{min:0,places:'0,2'}":"constraints :{min:0,places:0}";?>"
      <?php if ($readOnly or !$selection or !$hasWork) echo 'readonly'; ?>
      id="tokenQuantityValue_<?php echo $cpt;?>" onchange="dispatchTokenQuantityValueEvents(<?php echo $cpt;?>)">
      <?php echo $keyDownEventScript ; ?>

     </div>
  </td>
  <td>&nbsp;</td>
  <?php 
    $quantityMarkup=($selection)?$workTokenWork->workTokenMarkupQuantity:"";
    $totalQuantityMarkup+=($quantityMarkup!="")?$quantityMarkup:0;
  ?>
  <td style="text-align:center">
    <div dojoType="dijit.form.NumberTextBox" class="input" style="width:50px;" value="<?php echo $quantityMarkup; ?>"
      name="tokenQuantityMarkupValue[]" readonly 
      <?php // if ($readOnly) echo 'readonly';?>
      id="tokenQuantityMarkupValue_<?php echo $cpt;?>">
      <?php echo $keyDownEventScript;?>  
     </div>
  </td>
  <td>&nbsp;</td>
 <?php }  if($activeToken){?>
  <td style="text-align:center"> 
    <?php if (isNewGui()) {?>
    <div  id="billableSiwtched_<?php echo $cpt;?>" class="colorSwitch  <?php if (! $canUpdate) { ?>mblSwitchDisabled<?php }?>" data-dojo-type="dojox/mobile/Switch" value="<?php echo (($selection and $workTokenWork->billable!=1))?"off":"on";?>"
                    leftLabel="" rightLabel="" style="width:10px;position:relative;top:2px;z-index:99;"  >
      <script type="dojo/method" event="onStateChanged" >
  	     dijit.byId("billableToken_<?php echo $cpt;?>").set("checked",(this.value=="on")?true:false);
  	  </script>
    </div>
  	<?php }?>
    <div type="checkbox" dojoType="dijit.form.CheckBox" id="billableToken_<?php echo $cpt;?>"  
      name="billableToken[]" <?php if (isNewGui()) echo 'style="display:none;"';?> <?php echo ($selection and $workTokenWork->billable!=1)?"":"checked";?>>
      <script type="dojo/method" event="onChange" >
  	     dojo.byId("billableTokenInput_<?php echo $cpt;?>").value=(this.checked==true)?1:0;
  	  </script>
    </div>
    <input type="hidden" id="billableTokenInput_<?php echo $cpt;?>" name="billableTokenInput[]" value="<?php echo (($selection and $workTokenWork->billable!=1))?"0":"1";?>">
  </td>
 <?php }?>
</tr> 
<?php 
$total+=$work['work'];
}?>
</tbody>
</table>
</div>
<table style="<?php echo ($activeToken)?'width:1035px;':'width:100%;'?>">
  <tr>
    <td class="tabLabel" ><?php echo i18n('sum');?></td>
    <td></td>
    <?php if ($canUpdate) {?>
    <td style="word-space:nowrap;<?php echo ($activeToken)?'padding-left:13px;':'padding-left:4px;'?>">
      <div dojoType="dijit.form.NumberTextBox" id="dispatchWorkTotal" name="dispatchWorkTotal" 
          readonly class="input" style="width:50px;" value="<?php echo Work::displayImputation($total);?>"></div>
         <?php echo Work::displayShortImputationUnit();?>
    </td>
    <?php }?>
    <?php if($activeToken){?>
    <td style="text-align:right">
      <div dojoType="dijit.form.NumberTextBox" id="quantityTotal" name="quantityTotal" 
              readonly class="input" style="width:50px;margin-left:18px" value="<?php echo $totalQuantity;?>"></div>
    </td>
    <td >&nbsp;</td>
    <td style="text-align:left">
      <div dojoType="dijit.form.NumberTextBox" id="quantityMarkupTotal" name="quantityMarkupTotal" 
              readonly class="input" style="width:50px;margin-right:36px;" value="<?php echo $totalQuantityMarkup;?>"></div>
    </td>
    <?php }?>
  <tr>
    <td colspan="3">&nbsp;</td>
  </tr>
  <tr>
   <td style="<?php echo ($activeToken)?'width: 74%;padding-right: 130px;':'width: 75%;';?>" align="right" colspan="<?php echo ($activeToken)?'3':'2'?>">
     <button dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogDispatchWork').hide();" class="mediumTextButton">
       <?php echo ($canUpdate)?i18n("buttonCancel"):i18n("comboCloseButton");?>
     </button>
      <?php if ($canUpdate) {?>
     <button id="dialogDispatchWorkSubmit" dojoType="dijit.form.Button" type="submit" class="mediumTextButton"
       onclick="this.focus();protectDblClick(this);dispatchWorkSave();return false;" >
       <?php echo i18n("buttonOK");?>
     </button>
        <?php }?>
   </td>
   <td style="text-align: right;<?php echo ($activeToken)?'width: 26%;':'width: 25%;';?>" <?php echo ($activeToken)?'colspan="3"':''?>>
   <?php if ($canUpdate) {?>
   <?php if (isNewGui()) {?>
   <img class="roundedButtonNoBorder imageColorNewGui iconSize22" src="css/customIcons/new/iconAdd.svg" onClick="addDispatchWorkLine('<?php echo Work::displayShortWorkUnit();?>');" title="<?php echo  i18n('addLine');?>" />
   <?php } else {?>
   <img class="roundedButtonSmall" src="css/images/smallButtonAdd.png" onClick="addDispatchWorkLine('<?php echo Work::displayShortWorkUnit();?>');" title="<?php echo  i18n('addLine');?>" />
   <?php }?>
   <?php }?>
   </td>
 </tr>      
</table>
</form>
