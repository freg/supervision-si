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
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
require_once "../tool/planProjectSelect.php";
scriptLog('   ->/view/refreshSelectedProjectListDiv.php'); 

$isChecked = RequestHandler::getValue('isChecked');
$selectedProjectPlan = RequestHandler::getValue('selectedProjectPlan');
if(!$selectedProjectPlan){
  $isChecked='false';
}

?>
<?php echo planProjectSelectOpen(); ?>
                  <?php if(($selectedProjectPlan == ' ' or $selectedProjectPlan == '*') or $isChecked == 'false'){ ?>
                   <option value=" "><strong><?php echo i18n("allProjects");?></strong></option>
                   <?php }
                      $proj=null; 
                      if (sessionValueExists('planSelectedProjects')) {
                        $proj=getSessionValue('planSelectedProjects');
                      } else if (sessionValueExists('project')) {
                          $proj=getSessionValue('project');
                          if(pq_strpos($proj, ",")){
                          	$proj="*";
                          }
                      }
                      if ($proj=="*" or ! $proj) $proj=null;
                      $user=getSessionUser();
                      $wbsList=SqlList::getList('Project','sortOrder',$proj, true );
                      $sepChar=Parameter::getUserParameter('projectIndentChar');
                      if (!$sepChar) $sepChar='__';
                      else if ($sepChar=='no') $sepChar='';
                      $wbsLevelArray=array();
                      $projectClause = transformListIntoInClause(getSessionUser()->getListOfPlannableProjects());
                      if($isChecked == 'true'){
                        if(!pq_trim($selectedProjectPlan) or $selectedProjectPlan == '*')$selectedProjectPlan=0;
                      	$projectClause = "(".$selectedProjectPlan.")";
                      }
                      $inClause=" idProject in ". $projectClause;
                      $inClause.=" and idProject not in " . Project::getAdminitrativeProjectList();
                      $inClause.=" and refType= 'Project'";
                      $inClause.=" and idle=0";
                      $order="wbsSortable asc";
                      // Raw query : the loop reads two columns, and building one
                      // PlanningElement object per project costs sixty times more
                      $pe=new PlanningElement();
                      $peTable=$pe->getDatabaseTableName();
                      $list=array();
                      // Aliased in lower case : PostgreSQL folds unquoted identifiers
                      $resPe=Sql::query("select idProject as idproject, refName as refname from $peTable where $inClause order by $order");
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
                        $val = $sep.$projOb->refName;
                        ?>
                        <option value="<?php echo $projOb->idProject; ?>" ><?php if($isChecked == 'true'){ echo '<strong>';}?><?php echo $val; ?><?php if($isChecked == 'true'){ echo '</strong>';}?></option>      
                       <?php
                     }
                     echo planProjectSelectClose();
                   ?>
