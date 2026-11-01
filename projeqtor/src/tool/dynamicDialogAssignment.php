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
include_once ("../tool/projeqtor.php");
$currency=Parameter::getGlobalParameter('currency');
$currencyPosition=Parameter::getGlobalParameter('currencyPosition');
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
$idProject=RequestHandler::getId('idProject',false,null);
$refType=RequestHandler::getValue('refType',false,null);
$refId=RequestHandler::getId('refId',false,null);
$idRole=RequestHandler::getId('idRole',false,null);
$idResource = RequestHandler::getId('idResource',false,null);
$idResource = pq_trim($idResource);
$isTeam = RequestHandler::getBoolean('isTeam');
$isOrganization = RequestHandler::getBoolean('isOrganization');
$isResourceTeam = RequestHandler::getBoolean('isResourceTeam');
$isMaterial = RequestHandler::getBoolean('isMaterial');
$idAssignment=RequestHandler::getId('idAssignment',false,null);
$assignmentObj = new Assignment($idAssignment);
$unit=RequestHandler::getValue('unit',false,null);
$assignedIdOrigin=RequestHandler::getId('assignedIdOrigin',false,null);
$assignmentObjOrigin = new Assignment($assignedIdOrigin);
$validatedWorkPeOld = RequestHandler::getValue('validatedWorkPe',false,null);
$assignedWorkPeOld = RequestHandler::getValue('assignedWorkPe',false,null);
$realWork = RequestHandler::getNumeric('realWork',false,0);
$hoursPerDay=Work::getHoursPerDay();
$delay=null;
if ($assignmentObj->realWork==null){
  $assignmentObj->realWork="0";
}
if($assignmentObj->leftWork==null){
  $assignmentObj->leftWork="0";
}
$obj=new $refType($refId);
if($refType=="Meeting" || $refType=="PeriodicMeeting") {
	$delay=Work::displayWork(workTimeDiffDateTime('2000-01-01T'.$obj->meetingStartTime,'2000-01-01T'.$obj->meetingEndTime));
}
if($refType=="PokerSession") {
	$delay=Work::displayWork(workTimeDiffDateTime('2000-01-01T'.$obj->pokerSessionStartTime,'2000-01-01T'.$obj->pokerSessionEndTime));
}
$mode = RequestHandler::getValue('mode',false,true);

$elementList =($refType=="Meeting" || $refType=="PeriodicMeeting" || $refType=="PokerSession")?'idAffectable':'idResourceAll';
$critFld ='idProject';
$critVal =$idProject;
if($isTeam){
  $critFld =null;
  $critVal =null;
  $elementList = 'idTeam';
}
if($isOrganization){
  $critFld =null;
  $critVal =null;
  $elementList = 'idOrganization';
}

if($isResourceTeam){
    $critFld =null;
    $critVal =null;
    $elementList = 'idResourceTeam';
}

if($isMaterial){
	$critFld =null;
	$critVal =null;
	$elementList = 'idResourceMaterial';
}

// $arrayDefaultOffDays=array();
// if (Parameter::getGlobalParameter('OpenDayMonday')=='offDays') $arrayDefaultOffDays[]=1;
// if (Parameter::getGlobalParameter('OpenDayTuesday')=='offDays') $arrayDefaultOffDays[]=2;
// if (Parameter::getGlobalParameter('OpenDayWednesday')=='offDays') $arrayDefaultOffDays[]=3;
// if (Parameter::getGlobalParameter('OpenDayThursday')=='offDays') $arrayDefaultOffDays[]=4;
// if (Parameter::getGlobalParameter('OpenDayFriday')=='offDays') $arrayDefaultOffDays[]=5;
// if (Parameter::getGlobalParameter('OpenDaySaturday')=='offDays') $arrayDefaultOffDays[]=6;
// if (Parameter::getGlobalParameter('OpenDaySunday')=='offDays') $arrayDefaultOffDays[]=7;
$res=($refType=="Meeting" || $refType=="PeriodicMeeting" || $refType=="PokerSession")?'Affectable':'ResourceAll';
$resource=new $res($idResource);

if($resource->id  and $resource->isContact!='1'){
  $calendar = new CalendarDefinition($resource->idCalendarDefinition);
}else{
  $calendar = new CalendarDefinition();
}

$planningMode=null;
$peName=$refType.'PlanningElement';
if (property_exists($obj, $peName)) {
  $idPm=$obj->$peName->idPlanningMode;
  $pmObj=new PlanningMode($idPm);
  $planningMode=$pmObj->code;
}
$assRec=array();
if ($planningMode=='RECW') {
  for ($i=1;$i<=7;$i++) $assRec[$i]=null;
  $ar=new AssignmentRecurring();
  $arList=$ar->getSqlElementsFromCriteria(array('idAssignment'=>$idAssignment));
  foreach($arList as $ar) {
    $assRec[$ar->day]=$ar->value;
  }
}
$currencyLocal=Parameter::getGlobalParameter('currency');
$currencyPositionLocal=Parameter::getGlobalParameter('currencyPosition');
$convertionRate=1;
if ($obj and $obj->id and $obj->hasCurrency()) {
  $currencyLocal=Project::getProjectCurrency($obj->idProject);
  $currencyPositionLocal=Project::getProjectCurrencyPosition($obj->idProject);
  $convertionRate=$obj->getGlobalToLocalConversionRate();
}

$propReadonly=true;
$propChecked=false;
if (isset($pmObj) and (PlanningMode::isFixedDuration($pmObj->id) or PlanningMode::isRegularDuration($pmObj->id))) {
  $propReadonly=false;
  if ($mode=='add' and $pmObj->proportional) {
    $propChecked=true;
  } else if ($assignmentObj->proportional)  {
    $propChecked=true;
  }
}
?>
<form dojoType="dijit.form.Form" id='assignmentForm' jsid='assignmentForm' name='assignmentForm' onSubmit="return false;" style="overflow: auto;">    
         <script type="dojo/connect" event="onShow" args="evt">
           editAssignmentLoading=true; // PBER #7180 - avoid reset of function for Pool
           resourceListTransformation("assignmentIdResource");
           setTimeout("editAssignmentLoading=false;",500);           
         </script>
  <table>
    <tr>
      <td>
       
         <input id="assignmentId" name="assignmentId" type="hidden" value="<?php echo $idAssignment ;?>" />
         <input id="assignmentRefType" name="assignmentRefType" type="hidden" value="<?php echo $refType ;?>" />
         <input id="assignmentRefId" name="assignmentRefId" type="hidden" value="<?php echo $refId ;?>" />
         <input id="interventionActivityType" name="interventionActivityType" type="hidden" value="<?php echo $refType ;?>" />
         <input id="interventionActivityId" name="interventionActivityId" type="hidden" value="<?php echo $refId ;?>" />
         <input id="assignedIdOrigin" name="assignedIdOrigin" type="hidden" value="<?php echo $assignedIdOrigin ;?>" />
         <input id="assignedWorkOrigin" name="assignedWorkOrigin" type="hidden" value="<?php echo $assignmentObj->assignedWork ;?>" />
         <input id="leftWorkOrigin" name="leftWorkOrigin" type="hidden" value="<?php echo $assignmentObj->leftWork ;?>" />
         <input id="isTeam" name="isTeam" type="hidden" value="<?php echo $isTeam;?>" />
         <input id="isOrganization" name="isOrganization" type="hidden" value="<?php echo $isOrganization;?>" />
         <input id="isResourceTeam" name="isResourceTeam" type="hidden" value="<?php echo $isResourceTeam;?>" />
         <input id="isMaterial" name="isMaterial" type="hidden" value="<?php echo $isMaterial;?>" />
         <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
         <input id="planningMode" name="planningMode" type="hidden" value="<?php echo $planningMode;?>" />
         <input id="idPokerSession" name="idPokerSession" type="hidden" value="<?php echo $refId ;?>" />
      
         <table>
           <tr>
             <td class="dialogLabel" >
               <label for="assignmentIdResource" ><?php if($isTeam){  echo i18n("colIdTeam");}else if($isOrganization){  echo i18n("colIdOrganization");}else if($isResourceTeam){  echo i18n("ResourceTeam");}else if($isMaterial){  echo i18n("ResourceMaterial");}else{ echo i18n("colIdResource");}?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>  
             <td>
              <div dojoType="dijit.form.FilteringSelect"
              data-dojo-props="labelAttr:'label', labelType:'html', queryExpr: '*${0}*', autoComplete:false"
               <?php echo autoOpenFilteringSelect();?> 
              <?php $isSelectFonction = Parameter::getGlobalParameter('selectFonction'); ?>
                id="assignmentIdResource" name="assignmentIdResource" <?php if($planningMode=='MAN' and $mode=="edit"){ echo "readonly";}?>
                class="input" value="<?php echo $idResource;?>"
                onChange="<?php if($isSelectFonction == 'YES' and $elementList=='idResourceAll'){?>assignmentChangeResourceSelectFonction(<?php echo $convertionRate;?>);<?php }else{?> assignmentChangeResource(<?php echo $convertionRate;?>); <?php }?> assignmentChangeResourceTeamForCapacity();" <!--  remove -> refreshReccurentAssignmentDiv(this.value); for #10958 -->
                missingMessage="<?php echo i18n('messageMandatory',array(i18n('colIdResource')));?>" <?php echo ($realWork!=0 && $mode=='edit')?"readonly=readonly":"";?>>
                <?php if($mode=='edit'){                      
                          htmlDrawOptionForReference($elementList, $idResource,$obj,true,'idProject',$idProject,null,null,null,null,null,true);
                }else{
                          htmlDrawOptionForReference($elementList, null,$obj,false,$critFld,$critVal,null,null,null,null,null,true);
                }?>
               </div>  
             </td>
             <?php if($refType=="Meeting" || $refType=="PeriodicMeeting" || $refType=="PokerSession") {  ?>
             <td style="vertical-align: top">
               <button id="assignmentDetailButton" dojoType="dijit.form.Button" showlabel="false"
                 title="<?php echo i18n('showDetail')?>" iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                 <script type="dojo/connect" event="onClick" args="evt">
                    var canCreate=("<?php echo securityGetAccessRightYesNo('menuAffectable','create');?>"=="YES")?1:0;
                    showDetail('assignmentIdResource', canCreate ,'Affectable',false);
                 </script>
               </button>
             </td> 
             <?php }else if(Module::isModuleActive('moduleSkillManagement') and property_exists($refType, '_ActivitySkill') and !empty($obj->_ActivitySkill) and !$isTeam and !$isOrganization and !$isResourceTeam and !$isMaterial){ ?>
             <td style="vertical-align: top">
                 <button id="skillDetailButtonAss" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                   <script type="dojo/connect" event="onClick" args="evt">
                    var canCreate=("<?php echo securityGetAccessRightYesNo('menuAffectable','create');?>"=="YES")?1:0;
                    showResourceSkillList('<?php echo $obj->id;?>','<?php echo $critFld;?>','<?php echo $critVal;?>');
                   </script>
                 </button>
               </td> 
               <?php } ?> 
           </tr>
           <tr id="assignmentUniqueSelection" style="<?php echo (!$idResource or !$resource->isResourceTeam or $isResourceTeam or $isMaterial)?"display:none":"";?>">
            <td class="dialogLabel">&nbsp;</td>
            <td>
              <input title="<?php echo i18n('helpUniqueResource');?>"
                     dojoType="dijit.form.CheckBox" name="assignmentUnique" id="assignmentUnique"
                     onChange="assignmentChangeUniqueResource(this.checked);" <?php if (isNewGui()) echo 'class="whiteCheck"';?>
                     <?php echo ($assignmentObj->uniqueResource)?"checked=checked":"";?> />
              <label title="<?php echo i18n('helpUniqueResource');?>" style="float:none;<?php echo (isNewGui())?'position:relative;top:5px;':'';?>" for="attendantIsOptional" ><?php echo i18n("uniqueResource"); ?></label>
            </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="assignmentIdRole" ><?php echo i18n("colIdRole");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
              <div id="assignmentIdRoleDiv" dojoType="dijit.layout.ContentPane">
                <select dojoType="dijit.form.FilteringSelect" 
                <?php echo autoOpenFilteringSelect();?>
                  id="assignmentIdRole" name="assignmentIdRole"
                  class="input" required
                  
                  onChange="assignmentChangeRole(<?php echo $convertionRate;?>);" <?php echo ($realWork!=0 && $idRole)?"readonly=readonly":"";?>>                
                   <?php 
                   if($mode=='edit'){
                     if($isSelectFonction == 'YES' ){//and !$resource->isResourceTeam    // Florent ticket 5263
                        $critFld = 'id';
                        $critVals = array();
                        $vals = array();
                        foreach (SqlList::getListWithCrit('ResourceCost', array('idResource'=>$resource->id), 'idRole') as $idRoles) {
                          $vals[] = $idRoles;
                        }
                        $resTest=(get_class($resource)=='Affectable')?new ResourceAll($resource->id):$resource; 
                        if($resTest->id and !in_array($resTest->idRole, $vals))array_push($vals, $resTest->idRole);
                        $critVals[] = $vals;
                        htmlDrawOptionForReference('idRole', $idRole, null, true,$critFld,$critVals);
                     }else{
                      if ($resource->isResourceTeam) htmlDrawOptionForReference('idRole', $idRole, null, false);
                      else htmlDrawOptionForReference('idRole', $idRole, null, true);
                     }
                   } else {
                     htmlDrawOptionForReference('idRole', null, null, false);
                   }?>            
                 </select>
               </div>  
             </td>
           </tr>
           <?php $pe=new PlanningElement();
           $pe->idProject=(property_exists($obj, 'idProject'))?$obj->idProject:$idProject;
           $pe->setVisibility(); ?>
           <tr <?php echo ($pe->_costVisibility=='ALL' and $obj->showGlobalCurrency())?'':'style="display:none;"'?>>
             <td class="dialogLabel" >
               <label for="assignmentDailyCost" ><?php echo i18n("colCost");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <?php echo ($currencyPosition=='before')?$currency:''; ?>
               <div id="assignmentDailyCost" name="assignmentDailyCost" value="<?php echo ($mode=='edit')?$assignmentObj->dailyCost:'';?>" 
                 dojoType="dijit.form.NumberTextBox" 
                 constraints="{min:0}" 
                 style="width:97px"            
                 readonly >
                 <?php echo $keyDownEventScript;?>
                 <?php if ($obj->hasCurrency()) {?>
                 <?php $conversion=$obj->getGlobalToLocalConversionRate();?>
                 <script type="dojo/connect" event="onChange">
                   global=dijit.byId('assignmentDailyCost').get('value');     
                   var conversion=<?php echo $conversion;?>;
                   var localValue=calculateAmountFromConvertion(global,conversion,'assignmentDailyCostLocal');
                 </script>
                 <?php }?>
                 </div>
               <?php echo ($currencyPosition=='after')?$currency:'';
                     echo " / ";
                     echo i18n('shortDay'); ?>
             </td>
           </tr>
           <tr <?php echo ($pe->_costVisibility=='ALL' and $obj->hasCurrency())?'':'style="display:none;"'?>>
             <td class="dialogLabel" >
               <label for="assignmentDailyCostLocal" class="localLabelClass"><?php echo $assignmentObj->getColCaption("costLocal");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <?php echo ($currencyPositionLocal=='before')?'<span class="localLabelClass">'.$currencyLocal.'</span>':''; ?>
               <div id="assignmentDailyCostLocal" name="assignmentDailyCostLocal" value="<?php echo ($mode=='edit')?$assignmentObj->dailyCostLocal:'';?>" 
                 dojoType="dijit.form.NumberTextBox" class="localFieldClass"
                 constraints="{min:0}" 
                 style="width:97px"            
                 readonly >
                 <?php echo $keyDownEventScript;?>
                 </div>
               <?php echo ($currencyPositionLocal=='after')?'<span class="localLabelClass">'.$currencyLocal.'</span>':'';
                     echo " / ";
                     echo i18n('shortDay'); ?>
             </td>
           </tr>
           <tr id="assignmentRateRow" name="assignmentRateRow" <?php if (($resource->isResourceTeam and !$assignmentObj->uniqueResource and !$isResourceTeam and !$isMaterial and !$propChecked) or $planningMode=="MAN") echo 'style="display:none"';?>>
             <td class="dialogLabel" >
               <label for="assignmentRate" ><?php echo i18n("colRate");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php if($resource->isResourceTeam and !$assignmentObj->uniqueResource and !$isResourceTeam and !$isMaterial and !$propChecked){
               $assignmentObj->rate=$assignmentObj->capacity*100;
               if($assignmentObj->rate > 100)$assignmentObj->rate = 100;
             }?>
               <div id="assignmentRate" name="assignmentRate" value="<?php echo ($mode=='edit' and $planningMode!='RECW')?$assignmentObj->rate:"100";?>"
                 dojoType="dijit.form.NumberTextBox"
                 constraints="{min:0,max:100}"
                 style="width:97px;"
                 <?php if ($planningMode=='RECW') echo ' readonly';?>
                 missingMessage="<?php echo i18n('messageMandatory',array(i18n('colRate')));?>"
              <?php if (!$resource->isResourceTeam) { ?>  required="true" <?php } ?> >
                 <?php echo $keyDownEventScript;?>
                 </div>
             </td>
           </tr>
           <tr id="assignmentProportionalRow" name="assignmentProportionalRow" title="<?php echo i18n('hintProportional');?>">
             <td class="dialogLabel" >
               <label for="assignmentProportional" ><?php echo i18n("colProportional");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="assignmentProportional" name="assignmentProportional"
                 dojoType="dijit.form.CheckBox" type="checkbox" 
                 <?php echo ($propChecked)?" checked=checked ":""; ?>
                 <?php echo ($propReadonly)?"readonly=readonly":"";?> 
                 <?php if (isNewGui()) echo 'class="whiteCheck"';?>
                 >
                 <script type="dojo/connect" event="onChange">
                   if (dojo.byId('assignmentCapacityResourceTeam').style.display!="none") { // Resource Team
                     if (this.checked) dojo.byId('assignmentRateRow').style.display="table-row";
                     else dojo.byId('assignmentRateRow').style.display="none";
                   }
                   if (this.checked) {
                     dijit.byId("assignmentAssignedWork").set('readOnly',true);
                     dijit.byId("assignmentLeftWork").set('readOnly',true);
                     dojo.byId("assignmentAssignedWorkRow").title=dojo.byId("storedAssignedTitle").title;
                     dojo.byId("assignmentLeftWorkRow").title=dojo.byId("storedLeftTitle").title;
                   } else {
                     dijit.byId("assignmentAssignedWork").set('readOnly',false);
                     dijit.byId("assignmentLeftWork").set('readOnly',false);
                     dojo.byId("assignmentAssignedWorkRow").title='';
                     dojo.byId("assignmentLeftWorkRow").title='';
                   }
                 </script>
               </div>
               <div id="storedAssignedTitle" style="display:none" title="<?php echo i18n('hintProportionalAssignedWork');?>"></div>
               <div id="storedLeftTitle" style="display:none" title="<?php echo i18n('hintProportionalLeftWork');?>"></div>
               <div style="display:inline-block;position:relative;top:2px;font-size:80%" class='dialogLabel'><?php echo i18n('proportional');?></div>
             </td>
           </tr>
             <tr id="assignmentCapacityResourceTeam" name="assignmentCapacityResourceTeam" <?php if (! $resource->isResourceTeam or $assignmentObj->uniqueResource) echo 'style="display:none"';?>>
               <td class="dialogLabel" >
                 <label for="assignmentCapacity" ><?php echo i18n("colCapacity");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               </td>
               <td>
                 <?php if ($mode=='edit' and get_class($resource)!="Affectable" and $assignmentObj->capacity==0 and !$resource->isResourceTeam) round($assignmentObj->capacity=$resource->capacity*$assignmentObj->rate/100,1);
                       if ($assignmentObj->uniqueResource ) round($assignmentObj->capacity=1*$assignmentObj->rate/100,1);?>
                 <div id="assignmentCapacity" name="assignmentCapacity" value="<?php echo ($mode=='edit' && $assignmentObj->capacity)?$assignmentObj->capacity:"1";?>"
                   dojoType="dijit.form.NumberTextBox" 
                   style="width:97px" 
                   <?php if ($planningMode=='RECW') echo ' readonly';?>
                   missingMessage="<?php echo i18n('messageMandatory',array(i18n('colCapacity')));?>" 
                   required="true" >
                   <?php echo $keyDownEventScript;?>
                   </div>
               </td>
             </tr>
           
           <tr id="assignmentAssignedWorkRow" style="<?php if ($planningMode=='RECW') echo 'display:none;';?>" title="<?php echo i18n('hintProportionalAssignedWork');?>">
             <td class="dialogLabel" >
               <label for="assignmentAssignedWork" ><?php echo i18n("colAssignedWork");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="assignmentAssignedWork" name="assignmentAssignedWork" <?php if($planningMode=='MAN'){ echo "readonly";}?>
                 value="<?php if(($refType=='Meeting' || $refType=='PeriodicMeeting') && $mode=="add" && $obj->meetingStartTime && $obj->meetingEndTime){ 
                                  echo $delay;
                              }else if (($refType=="PokerSession") && $mode=="add" && $obj->pokerSessionStartTime && $obj->pokerSessionEndTime){
                                  echo $delay;
                              }else if ($mode=="edit"){
                                  echo Work::displayWork($assignmentObj->assignedWork);
                              } else if($mode=="add" and $planningMode != 'MAN') { 
                                  $assignedWork = GeneralWork::convertWork($validatedWorkPeOld)-GeneralWork::convertWork($assignedWorkPeOld);
                                  if($assignedWork < 0 or $planningMode=='RECW'){
                                    echo "0";
                                  } else {
                                    echo Work::displayWork($assignedWork);
                                  }                             
                              } else if($mode=="divide"){
                                  echo Work::displayWork($assignmentObjOrigin->leftWork/2);
                              }else{
                                echo '0';
                              }
                 ?>" 
                 dojoType="dijit.form.NumberTextBox" 
                 constraints="{min:0,max:9999999.99}" 
                 style="width:97px"
                 <?php if ($planningMode=='RECW' or $propChecked) echo ' readonly';?>
                 onchange="assignmentUpdateLeftWork('assignment');"
                 onblur="assignmentUpdateLeftWork('assignment');" >
                 <?php echo $keyDownEventScript;?>
                 </div>
               <input id="assignmentAssignedUnit" name="assignmentAssignedUnit" value="<?php echo $unit ;?>" readonly tabindex="-1"
                 xdojoType="dijit.form.TextBox" 
                 class="display" style="width:15px; background-color:transparent; color:#000000; border:0px;"/>
               <input type="hidden" id="assignmentAssignedWorkInit" name="assignmentAssignedWorkInit" value="<?php echo($mode=="edit")?Work::displayWork($assignmentObj->assignedWork):"";?>" 
                 style="width:97px"/>  
             </td>    
           </tr>
           <tr style="<?php if ($planningMode=='RECW') echo 'display:none;';?>">
             <td class="dialogLabel" >
               <label for="assignmentRealWork" ><?php echo i18n("colRealWork");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="assignmentRealWork" name="assignmentRealWork" value="<?php echo ($mode=="edit")?Work::displayWork($assignmentObj->realWork):"0";?>"  
                 dojoType="dijit.form.NumberTextBox" 
                 constraints="{min:0,max:9999999.99}" 
                 style="width:97px" readonly >
                 <?php echo $keyDownEventScript;?>
                 </div>
               <input id="assignmentRealUnit" name="assignmentRealUnit" value="<?php echo $unit ;?>" readonly tabindex="-1"
                 xdojoType="dijit.form.TextBox" 
                 class="display" style="width:15px;background-color:transparent; color:#000000; border:0px;"/>
             </td>
           </tr>
           <tr id="assignmentLeftWorkRow" style="<?php if ($planningMode=='RECW') echo 'display:none;';?>" title="<?php echo i18n('hintProportionalLeftWork');?>">
             <td class="dialogLabel" >
               <label for="assignmentLeftWork" ><?php echo i18n("colLeftWork");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php $habil=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile' => $user->getProfile($idProject),'scope' => 'lockedLeftWork'));?>
               <div id="assignmentLeftWork" name="assignmentLeftWork" <?php if($planningMode=='MAN' or $habil->rightAccess == '2'){ echo "readonly";}?>                 
                 value="<?php if(($refType=='Meeting' || $refType=='PeriodicMeeting') && $mode=="add" && $obj->meetingStartTime && $obj->meetingEndTime){ 
                                  echo $delay;
                              }else if (($refType=="PokerSession") && $mode=="add" && $obj->pokerSessionStartTime && $obj->pokerSessionEndTime){
                                  echo $delay;
                              } else if($mode=="edit"){
                                  echo Work::displayWork($assignmentObj->leftWork);
                              } else if($mode=="divide"){
                                  echo Work::displayWork($assignmentObjOrigin->leftWork/2);                                                       
                              } else if($planningMode != 'MAN') {
                                  $assignedWork = GeneralWork::convertWork($validatedWorkPeOld)-GeneralWork::convertWork($assignedWorkPeOld);
                                    if($assignedWork < 0 or $planningMode=='RECW'){
                                      echo "0";
                                    } else {
                                      echo Work::displayWork($assignedWork) ;
                                  }
                              }else{
                                echo '0';
                              } 
                 ?>" 
                 dojoType="dijit.form.NumberTextBox" 
                 constraints="{min:0,max:9999999.99}"
                 <?php if ($planningMode=='RECW' or $propChecked) echo ' readonly';?> 
                 onchange="assignmentUpdatePlannedWork('assignment');"
                 onblur="assignmentUpdatePlannedWork('assignment');"  
                 style="width:97px" >
                 <?php echo $keyDownEventScript;?>
                 <script type="dojo/connect" event="onChange">
                   if (this.value>0) {
                     dijit.byId("assignmentIdle").set("checked",false);
                     dijit.byId("assignmentIdle").set("readOnly",true); 
                   } else {
                     dijit.byId("assignmentIdle").set("readOnly",false);
                   }
                 </script>
                 </div>
               <input id="assignmentLeftUnit" name="assignmentLeftUnit" value="<?php echo $unit ;?>" readonly tabindex="-1"
                 xdojoType="dijit.form.TextBox" 
                 class="display" style="width:15px;background-color:transparent; color:#000000; border:0px;"/>
               <input type="hidden" id="assignmentLeftWorkInit" name="assignmentLeftWorkInit" value="<?php echo ($mode=="edit")?Work::displayWork($assignmentObj->leftWork):"0";?>" 
                 style="width:97px"/>  
             </td>
           </tr>
           <tr style="<?php if ($planningMode=='RECW') echo 'display:none;';?>">
             <td class="dialogLabel" >
               <label for="assignmentPlannedWork" ><?php echo i18n("colPlannedWork");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="assignmentPlannedWork" name="assignmentPlannedWork"                  
                 value="<?php if(($refType=='Meeting' || $refType=='PeriodicMeeting') && $mode=="add" && $obj->meetingStartTime && $obj->meetingEndTime){ 
                                  echo $delay;
                              }else if (($refType=="PokerSession") && $mode=="add" && $obj->pokerSessionStartTime && $obj->pokerSessionEndTime){
                                  echo $delay;
                              } else if($planningMode != 'MAN') {
                                  $assignedWork = GeneralWork::convertWork($validatedWorkPeOld)-GeneralWork::convertWork($assignedWorkPeOld);
                                  if($assignedWork < 0){
                                    echo "0";
                                  } else {
                                    echo Work::displayWork($assignedWork) ;
                                  }
                              }else{
                                echo '0';
                              }  
                 ?>" 
                 dojoType="dijit.form.NumberTextBox" 
                 constraints="{min:0,max:9999999.99}" 
                 style="width:97px" readonly > 
                 <?php echo $keyDownEventScript;?>
                 </div>
               <input id="assignmentPlannedUnit" name="assignmentPlannedUnit" value="<?php echo $unit;?>" readonly tabindex="-1"
                 xdojoType="dijit.form.TextBox" 
                 class="display" style="width:15px;background-color:transparent; border:0px;"/>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="assignmentIdle" ><?php echo i18n("colIdle");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <?php $checked=$assignmentObj->idle;
                     $readonly=0;
                     if ($obj->idle) {
                       $checked=1;
                       $readonly=1;
                     }
                     if ($assignmentObj->leftWork > 0) $readonly=1; 
                     ?>
               <div id="assignmentIdle" name="assignmentIdle" <?php echo ($checked)?" checked=checked ":""; ?>
                 dojoType="dijit.form.CheckBox" type="checkbox" <?php echo ($readonly)?"readonly=readonly":"";?> <?php if (isNewGui()) echo 'class="whiteCheck"';?>
                 onclick="if (dijit.byId('assignmentLeftWork').get('value')>0) {dojo.byId('assignmentIdleErrorMsg').innerHTML=i18n('errorIdleWithLeftWork');return false;}"
               >
               </div>
               <span style="color:red" id="assignmentIdleErrorMsg"></span>
             </td>    
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="assignmentComment" ><?php echo i18n("colComment");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <input id="assignmentComment" name="assignmentComment" value="<?php echo htmlEncode($assignmentObj->comment);?>"  
                 dojoType="dijit.form.Textarea" style="max-height:200px"
                 class="input" 
                 /> 
             </td>
           </tr>
         </table>       
         
       <div id="optionalAssignmentDiv" style="<?php if ($refType=="Meeting" || $refType=="PeriodicMeeting" || $refType=="PokerSession"){echo "display:block;";}else {echo "display:none;";}?>">
        <table style="margin-left:143px;">
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
            <td class="dialogLabel">&nbsp;</td>     
            <td>
              <input dojoType="dijit.form.CheckBox" name="attendantIsOptional" id="attendantIsOptional" 
              <?php echo ($mode=="edit" && $assignmentObj->optional==1)?"checked=checked":"";?> <?php if (isNewGui()) echo 'class="whiteCheck"';?>/>
              <label style="float:none" for="attendantIsOptional" ><?php echo i18n("attendantIsOptional"); ?></label>
            </td>
           <tr>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
           </tr>
        </table>
      </div>
         
      <div dojoType="dijit.layout.ContentPane" id="recurringAssignmentDiv" style="<?php if ($planningMode=='RECW'){echo "display:block;";}else {echo "display:none;";}?>">
        <table style="margin-left:143px;">
          <tr><td colspan="7">&nbsp;</td></tr>
          <tr>
            <td colspan="7" class="section"><?php echo i18n("sectionRecurringWeek");?></td>
          </tr>
          <tr>
            <?php for ($i=1; $i<=7; $i++) {?>
            <td class="dialogLabel" style="text-align:center"><?php echo i18n('colWeekday' . $i);?></td>
            <?php }?>
          </tr>
          <tr>
            <?php for ($i=1; $i<=6; $i++) {?>
            <td>
            <?php  $value=(isset($assRec[$i]))?Work::displayWork($assRec[$i]):0;
                    $dayofweek = 'dayOfWeek'.$i;?>
              <div dojoType="dijit.form.NumberTextBox"  style="width:53px;" name="recurringAssignmentW<?php echo $i;?>" id="recurringAssignmentW<?php echo $i;?>" value="<?php echo $value;?>" 
              constraints="{min:0,max:999.99}" class="input <?php if ($calendar->$dayofweek == 1) echo ' offDay';?>" >
              <?php echo $keyDownEventScript;?> 
              </div>
            </td>
            <?php }?>
            <td>
            <?php  $value=(isset($assRec[7]))?Work::displayWork($assRec[7]):0;?>
              <div dojoType="dijit.form.NumberTextBox"  style="width:53px;" name="recurringAssignmentW7" id="recurringAssignmentW7" value="<?php echo $value;?>" 
              constraints="{min:0,max:999.99}" class="input <?php if ($calendar->dayOfWeek0 == 1) echo ' offDay';?>" >
              <?php echo $keyDownEventScript;?> 
              </div>
            </td>
          </tr>
          <tr>
            <td colspan="2">
              <button class="<?php echo (isNewGui())?'':'roundedVisibleButton';?>" dojoType="dijit.form.Button" type="button" >
              <script type="dojo/connect" event="onClick" >
                var val1=dijit.byId('recurringAssignmentW1').get('value');
                for (var i=2; i<=7; i++) {
                  if (! dojo.hasClass('widget_recurringAssignmentW'+i,'offDay')) dijit.byId('recurringAssignmentW'+i).set("value",val1);
                }
              </script>
               <?php echo i18n("copy");?>
              </button>
            </td>
            <td colspan="5" style="text-align:right">
            <?php echo i18n('paramWorkUnit').'&nbsp;=&nbsp;'.i18n(Work::getWorkUnit());?> 
            </td>
          </tr> 
           <tr><td colspan="5">&nbsp;</td></tr>
        </table>
      </div>
      </td>
    </tr>
    <?php if($mode=='edit' and $planningMode=='MAN' and ! $assignmentObj->idle){  ?>
    <tr>
      <td align="center">
        <div id="plannedWorkManualAssignmentDiv" style="padding-top:10px;padding-bottom:10px;">
        <?php 
        $listResource=array($idResource);
        $listMonth=array();
        $date = date('m');
        $year = date('Y');
        $diffDate = $date-7;
        if($diffDate<=0){
          $maxDate=$diffDate+12;
          for($i=$date; $i<=$maxDate; $i++){
	         array_push($listMonth, $year.$i);
          }
        }else{
          for($i=$date; $i<=12; $i++){
          	array_push($listMonth, $year.$i);
          }
          for($i=1; $i<=$diffDate; $i++){
          	array_push($listMonth, ($year+1).$i);
          }
        }
        $size=20;
        PlannedWorkManual::setSize($size);
        PlannedWorkManual::drawTable('assignment',$idResource, $listMonth, $refType.'#'.$refId, false);
        ?>
        </div>
        <input type='hidden' id="plannedWorkManualAssignmentSize" value="<?php echo $size;?>"/>
        <input type='hidden' id="plannedWorkManualAssignmentResourceList" value="<?php echo implode(',',$listResource);?>"/>
        <input type='hidden' id="plannedWorkManualAssignmentMonthList" value="<?php echo implode(',',$listMonth);?>"/>
      </td>
    </tr>
    <?php }?>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogAssignmentAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAssignment').hide();" <?php if($planningMode=='MAN' and $mode=="edit"){ echo "disabled";}?>>
          <?php echo i18n("buttonCancel");?>
        </button>
        <?php if ($planningMode=='MAN' and $mode == "edit"){
          $buttonName = i18n("buttonOK");
        }else{
          $buttonName = i18n('saveLeavesSystemHabilitation');
        }?>
        <button class="mediumTextButton" dojoType="dijit.form.Button" id="dialogAssignmentSubmit" <?php if(!pq_trim($idResource)){echo 'disabled';}?> type="submit" onClick="protectDblClick(this);saveAssignment();return false;">
          <?php echo $buttonName;?>
        </button>
      </td>
    </tr>
  </table>
<?php if ($assignmentObj->uniqueResource and $assignmentObj->id) {
  echo '<div style="position:relative;top:10px;width:80%;left:10%;max-height: 300px;overflow-y: auto;">';
  AssignmentSelection::drawListForAssignment($assignmentObj->id, $assignmentObj->realWork);
  echo '</div><br/>';
}?>
</form>