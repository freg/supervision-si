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
require_once "../tool/planProjectSelect.php";
?>
<table>
<tr>
<td>
<form id='dialogPlanForm' name='dialogPlanForm' onSubmit="return false;">
<table>
<tr>
<td class="dialogLabel">
<label for="idProjectPlan" ><?php echo i18n("colIdProject") ?>&nbsp;:&nbsp;</label>
             </td>
             <td>
             <?php 
                $proj=null; 
                if (sessionValueExists('planSelectedProjects')) {
                  $proj=getSessionValue('planSelectedProjects');
                } else if (sessionValueExists('project')) {
                    $proj=getSessionValue('project');
                } else {
                  $defaultProject=Parameter::getUserParameter('defaultProject');
                  if (is_numeric($defaultProject)) $proj=$defaultProject;
                }
                $idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
                if($proj=="*" and $idFavoriteProjectList){
                  $favoriteProjectArray = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$idFavoriteProjectList), 'idProject');
                  $proj = implode(',', $favoriteProjectArray);
                }
                if ($proj=="*" or ! $proj) $proj=null;
                ?>
                <div dojoType="dijit.layout.ContentPane" id="selectProjectList" style="overflow:unset">
<?php echo planProjectSelectOpen();
                   // Selection is marked on the options themselves : the widget does
                   // not apply its value attribute to a multiple select.
                   // A single blank means "all projects", so it selects no project.
                   $planSelected=pq_trim($proj);
                   $planSelectedIds=($planSelected)?pq_explode(',', $planSelected):array();
                   ?>
                   <option value=" "<?php echo ($planSelected)?'':' selected';?>><span style="font-weight:bold"><?php echo i18n("allProjects");?></span></option>
                   <?php
                      $user=getSessionUser();
                      $wbsList=SqlList::getList('Project','sortOrder',$proj, true );
                      $sepChar=Parameter::getUserParameter('projectIndentChar');
                      if (!$sepChar) $sepChar='__';
                      else if ($sepChar=='no') $sepChar='';
                      $wbsLevelArray=array();
                      $inClause=" idProject in ". transformListIntoInClause(getSessionUser()->getListOfPlannableProjects());
                      $inClause.=" and idProject not in " . Project::getAdminitrativeProjectList();
                      $inClause.=" and refType= 'Project'";
                      $inClause.=" and idle=0";
                      // Raw query : the loop reads two columns, and building one
                      // PlanningElement object per project costs sixty times more
                      $pe=new PlanningElement();
                      $peTable=$pe->getDatabaseTableName();
                      $list=array();
                      // Aliased in lower case : PostgreSQL folds unquoted identifiers
                      $resPe=Sql::query("select idProject as idproject, refName as refname from $peTable where $inClause order by wbsSortable asc");
                      while ($linePe=Sql::fetchLine($resPe)) {
                        $list[]=(object)array('idProject'=>$linePe['idproject'], 'refName'=>$linePe['refname']);
                      }
                      foreach ($list as $projOb){
                        if (isset($wbsList[$projOb->idProject])) {
                          $wbs=$wbsList[$projOb->idProject];
                        } else {
                          $wbs='';
                        }
                        $wbsTest=$wbs;
                        $level=1;
                        while (pq_strlen($wbsTest)>3) {
                          $wbsTest=pq_substr($wbsTest,0,pq_strlen($wbsTest)-6);
                          if (pq_array_key_exists($wbsTest, $wbsLevelArray)) {
                            $level=$wbsLevelArray[$wbsTest]+1;
                            $wbsTest="";
                          }
                        }
                        $wbsLevelArray[$wbs]=$level;
                        $sep='';
                        for ($i=1; $i<$level;$i++) {$sep.=$sepChar;}
                        $val = $sep.htmlEncode($projOb->refName);
                        $selected="";
                        ?>
                        <option value="<?php echo $projOb->idProject; ?>"<?php echo (in_array($projOb->idProject, $planSelectedIds))?' selected':'';?>><?php echo $val; ?></option>
                       <?php
                     }
                     echo planProjectSelectClose();
                   ?>
              </div>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td class="dialogLabel"  >
               <label for="startDatePlan" ><?php echo i18n("colStartDate") ?>&nbsp;:&nbsp;</label>
             </td>
             <td >
               <div dojoType="dijit.form.DateTextBox" 
                 id="startDatePlan" name="startDatePlan" 
                 constraints="{datePattern:browserLocaleDateFormatJs}"
                 invalidMessage="<?php echo i18n('messageInvalidDate')?>" 
                 type="text" maxlength="10" 
                 style="width:100px; text-align: center;" class="input"
                 required="true"
                 hasDownArrow="false"
                 missingMessage="<?php echo i18n('messageMandatory',array(i18n('colStartDate')));?>"
                 value="<?php echo getSessionValue('startDatePlan',date('Y-m-d'));?>" >
                 <script type="dojo/method" event="onChange" >
                   current=dijit.byId('startDatePlan').get("value");
                   current=JSGantt.formatDateStr(current,'yyyy-mm-dd');
                   dojo.byId('planStartDate').value=current;
                   saveDataToSession('startDatePlan',current);
  		             </script>
               </div>
             </td>
           </tr>
           <?php 
            $canPlanWithOveruse=false; 
            $right=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$user->getProfile(),'scope'=>'planningWithOveruse'));
            if($right->rightAccess==1){
              $canPlanWithOveruse=true;
            }
            if ($canPlanWithOveruse) {?>
		       <tr style="height:30px">
				     <td class="dialogLabel" >		   
				     </td>
             <td title="<?php echo i18n("helpPlanWithInfiniteCapacity");?>">
               <table>
                <tr>
                  <td>
                    <div dojoType="dijit.form.CheckBox" type="checkbox" role="checkbox" class="dijit dijitReset dijitInline dijitCheckBox"
                     id="infinitecapacity" name="infinitecapacity"
                     <?php 
                     if((Parameter::getUserParameter('modeSurbooking')=="YES") || (Parameter::getUserParameter('modeSurbooking')=="NO") ){
                       $ParamDefaultModeSurbooking=Parameter::getUserParameter('modeSurbooking');
                     }else{
                       $ParamDefaultModeSurbooking=Parameter::getGlobalParameter('checkedSurbookingDefault');
                     }
                     if(($ParamDefaultModeSurbooking=='YES')){ echo ' checked="checked" ';}?>
                     style="user-select: none;margin-right: 5px;" class="input">
                     <script type="dojo/method" event="onClick" >
                       current=dijit.byId('infinitecapacity').get("value");
  		                   if (current!=="on" && dijit.byId("infinitecapacityCritical")) dijit.byId("infinitecapacityCritical").set("checked",false);
                       saveUserParameter('modeSurbooking',((this.checked)?'YES':'NO'));
                       if (! this.checked) saveDataToSession('modeSurbookingCritical','NO');
  		               </script>
                     </div>
                   </td>
                   <td class="dialogLabel" style="white-space:nowrap"><label for="infinitecapacity" style="width:50px"><?php echo i18n("planWithInfiniteCapacity");?></label></td>
                </tr>
               </table>             
             </td>
           </tr>
           <?php if (isset($paramCriticalPlan) and $paramCriticalPlan===true) {?>
           <tr style="height:30px">
				     <td class="dialogLabel" >		   
				     </td>
             <td title="<?php echo i18n("helpPlanWithInfiniteCapacityCritical");?>">
               <table>
                <tr>
                  <td>
                    <div dojoType="dijit.form.CheckBox" type="checkbox" role="checkbox" class="dijit dijitReset dijitInline dijitCheckBox"
                     id="infinitecapacityCritical" name="infinitecapacityCritical"
                     <?php 
                     if((Parameter::getUserParameter('modeSurbooking')=="YES") ){
                       $ParamModeSurbookingCritical=getSessionValue('modeSurbookingCritical');
                     }else{
                       $ParamModeSurbookingCritical='NO';
                       unsetSessionValue('modeSurbookingCritical');
                     }
                     if($ParamModeSurbookingCritical=='YES'){ echo ' checked="checked" ';}?>
                     style="user-select: none;margin-right: 5px;" class="input">
                     <script type="dojo/method" event="onClick" >
                       current=dijit.byId('infinitecapacityCritical').get("value");
  		                   if (current==="on" && dijit.byId("infinitecapacity")) dijit.byId("infinitecapacity").set("checked",true);
                       saveDataToSession('modeSurbookingCritical',((this.checked)?'YES':'NO'));
  		                 </script>
                     </div>
                   </td>
                   <td class="dialogLabel" style="white-space:nowrap"><label for="infinitecapacityCritical" style="width:50px"><?php echo i18n("planWithInfiniteCapacityCritical");?></label></td>
                </tr>
               </table>             
             </td>
           </tr>
           <?php }?>
           <?php }?>
           <tr style="height:30px">
             <td>
             </td>
             <td>
               <table>
                <tr>
                  <td>
                    <div dojoType="dijit.form.CheckBox" type="checkbox" id="onlyCheckedProject" name="onlyCheckedProject" 
                      style="margin-right: 5px;" onChange="showSelectedProject(this.checked);"></div>
                  </td>
                  <td class="dialogLabel" style="white-space:nowrap"><label for="onlyCheckedProject" style="width:50px"><?php echo i18n("showSelectedProject"); ?></label></td>
                </tr>
               </table>
             </td>
           </tr>
    <?php if(Parameter::getGlobalParameter('paramWithCriticalPath')!="NO"){
            $paramCriticalPath=Parameter::getGlobalParameter('paramWithCriticalPath');
            $paramCriticalPathGlobal=($paramCriticalPath=='false' or $paramCriticalPath===false)?false:true;
            $paramCriticalPathUser=Parameter::getUserParameter('planWithCriticalPath');
            ?>
           <tr style="height:30px">
             <td>
             </td>
             <td title="<?php echo i18n("CalculateCriticalPath");?>">
               <table>
                <tr>
                  <td>
                    <div dojoType="dijit.form.CheckBox" type="checkbox" id="checkboxCalculateCriticalPath" name="checkboxCalculateCriticalPath" 
                    <?php if ($paramCriticalPathGlobal==false) echo " readonly=readonly "; ?>
                    <?php if ($paramCriticalPathUser=='1') echo 'checked="true"';?>
                      style="margin-right: 5px;" onChange="saveUserParameter('planWithCriticalPath',((this.checked)?'1':'0')); if (this.checked && dijit.byId('criticalPathPlanning')) dijit.byId('criticalPathPlanning').set('value','on');"></div>
                  </td>
                  <td class="dialogLabel" style="white-space:nowrap"><label for="checkboxCalculateCriticalPath" style="width:50px"><?php echo i18n("CalculateCriticalPath"); ?></label></td>
                </tr>
               </table>
             </td>
           </tr>
          <?php }?>
           <?php 
           $user=getSessionUser();
           $priority=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$user->idProfile,'scope'=>'feedingOfTheReal'));
           if( $priority and ($priority->rightAccess == 1)){
           ?>
           <tr style="height:30px">

             <td class="dialogLabel" >
               <label style="width:200px;display:none;" for="allowAutomaticFeedingOfTheReal" ><?php echo i18n("allowAutomaticFeedingOfTheReal").'&nbsp;:' ?></label>
             </td>
             <td width="200px;" >
               <div title="<?php echo i18n('allowAutomaticFeedingOfTheReal')?>" dojoType="dijit.form.CheckBox" style="margin-left:5px;margin-top:2px;display:none;"
                    class="" type="checkbox" id="allowAutomaticFeedingOfTheReal" name="allowAutomaticFeedingOfTheReal"   
                    <?php if (Parameter::getGlobalParameter('automaticFeedingOfTheReal')=='YES') { echo ' checked="checked" '; }?> >
		           </div>&nbsp;
             </td>
           </tr>
           <?php } ?>
           <tr><td></td><td>&nbsp;</td></tr>
         </table>    
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogPlanAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="cancelPlan();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogPlanSubmit" onclick="protectDblClick(this);plan(true);return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>