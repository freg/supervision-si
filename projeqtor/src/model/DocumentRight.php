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
 * Habilitation defines right to the application for a menu and a profile.
 */ 
require_once('_securityCheck.php');
class DocumentRight extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  public $idDocumentDirectory;
  public $idProfile;
  public $idAccessMode;
  
  
  
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

  
 static function drawAllDocumentRight(){
   $columnList=SqlList::getList('profile');
   $nbProf=count($columnList);
   $nbcolumn=$nbProf+2;
   $user=getSessionUser();
   $dR=new DocumentRight();
   $lstDocRDraw=array();
   $where='1=1';
   $documentDirectory= new DocumentDirectory();
   $classDirectory=get_class($documentDirectory);
   
   $lstDocDirectoty=$documentDirectory->getSqlElementsFromCriteria(null,null,$where,'location');
   $destinationWidth=RequestHandler::getNumeric('destinationWidth')-(RequestHandler::getNumeric('destinationWidth')*0.05)-15;
   $tableWidth=$destinationWidth*0.9;
   $tableMargin=$destinationWidth*0.05;
   
   
   $widthSelect=intval($destinationWidth/($nbcolumn)-30);
   if(!empty($lstDocDirectoty)){
     echo '       <table class="crossTable" style="margin-left:'.$tableMargin.'px;margin-top:45px;">';
     echo '         <tr>';
     echo '             <td class="tabLabel">'.i18n('colName').'</td> <td class="tabLabel">'.i18n('colIdDocumentDirectory').'</td>';
                      foreach ($columnList as $col) {
     echo '             <td class="tabLabel">' . $col . '</td>';
                      }
     echo '           <td></td>';
     echo '         </tr>';
                    foreach ($lstDocDirectoty as $id=>$docD){
                      $lst=array();
                      $lstDocRight=array();
                      $newProfList=$columnList;
                      $clause=array('idDocumentDirectory'=>$docD->id);
                      $lst=$dR->getSqlElementsFromCriteria($clause);
                      $rightUpdate=securityGetAccessRightYesNo('menu'.$classDirectory,'update',$docD);
                      $rightRead=securityGetAccessRightYesNo('menu'.$classDirectory,'read',$docD);
                      foreach ($lst as $idDocR=>$docRight){
                          if(pq_array_key_exists($docRight->idProfile, $newProfList)){
                            unset($newProfList[$docRight->idProfile]);
                          }
                          $lstDocRight[$docRight->idProfile]=$docRight;
                      }
                      if($rightUpdate=="YES" or $rightRead=="YES"){
                        $goto='';
                        $style='';
                        if ( securityCheckDisplayMenu(null, $classDirectory) and $rightRead=="YES") {
                          $goto=' onClick="gotoElement(\''.$classDirectory.'\',\''.htmlEncode($docD->id).'\');" ';
                        }
                        echo '         <tr>';
                        echo '           <td class="crossTableLine" title="'.$docD->name.'" style="width:'.$widthSelect.'px;padding-right:10px;"><label class="label classLinkName " '.$goto.' style="text-align :left;">'.$docD->name .'</label></td>';
                        echo '           <td class="crossTableLine" title="'.$docD->name.'" style="width:'.$widthSelect.'px;padding-right:10px;"><label class="label classLinkName " '.$goto.' style="text-align :left;">'.$docD->location.'</label></td>';
                        foreach ($columnList as $id=>$col) {
                          if(pq_array_key_exists($id,$newProfList)){
                              if(!isset($lstNewDocRDraw))$lstNewDocRDraw=true;
                              $name="newDocumentRight_" .$docD->id."_".$id ;
                              $lstNewDocRight[]=$docD->id."_".$id;
                              echo '<td class="crossTablePivot">';
                              echo '  <select dojoType="dijit.form.FilteringSelect" class="input" '.(($rightUpdate=='NO' and $rightRead=='YES')?"readonly":"");
                              echo '     onchange="setLstDocumentRight(\'lstNewDocRight\',\''.$docD->id.'_'.$id .'\');"; ';
                              echo      autoOpenFilteringSelect();
                              echo '    style="width:'.$widthSelect.'px !important;min-width:80px; font-size: 80%;" id="' . $name . '" name="' . $name . '" >';
                              htmlDrawOptionForReference('idAccessProfile',9, null, true);
                              echo '  </select>';
                              echo '</td>';
                           }else if(pq_array_key_exists($id, $lstDocRight)){
                                  $docR=$lstDocRight[$id];
                                  if(!isset($lstDocRDraw))$lstDocRDraw=true;
                                  $name="documentRight_" . $docR->id ;
                                  echo '<td class="crossTablePivot">';
                                  echo '  <select dojoType="dijit.form.FilteringSelect" class="input" '.(($rightUpdate=='NO' and $rightRead=='YES')?"readonly":"");
                                  echo '     onchange="setLstDocumentRight(\'lstDocRight\',\''.$docR->id .'\');"; ';
                                  echo      autoOpenFilteringSelect();
                                  echo '    style="width:'.$widthSelect.'px !important;min-width:80px; font-size: 80%;" id="' . $name . '" name="' . $name . '" >';
                                  htmlDrawOptionForReference('idAccessProfile', $docR->idAccessMode, null, true);
                                  echo '  </select>';
                                  echo '</td>';
                          }
                        }
                        echo '           <td>&nbsp;&nbsp;&nbsp;</td>';
                        echo '         </tr>';
                      }
                    }
     
     echo '       </table>';
     if(isset($lstDocRDraw))echo '         <input id="lstDocRight" name="lstDocRight" value="" type="hidden" />';
     if(isset($lstNewDocRDraw))echo '         <input id="lstNewDocRight" name="lstNewDocRight" value="'.((!empty($lstNewDocRight))?implode(',', $lstNewDocRight):'').'" type="hidden" />';
     if(!isset($lstDocRDraw) and !isset($lstNewDocRDraw))echo '<div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;border-right: 1px solid grey;">'.i18n('noDataFound').'</div>';

   }else {
     echo '<table style="width:90%; margin-bottom:10px;margin-right:5%;margin-left:5%;margin-top:15px;">';
     echo '   <tr>';
     echo '    <td >';
     echo '    <div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;width:100%;border-right: 1px solid grey;">'.i18n('noDataFound').'</div>';
     echo '    </td>';
     echo '   </tr>';
     echo '</table>';
   }

 return ;
  }
  
  static  function drawDocumentRight($docDirect,$rightRead,$rightUpdate,$dR,$classDR) {
    $columnList=SqlList::getList('profile');
    $nbProf=count($columnList);
    $newProfList=$columnList;
    $lstNewDocRight=array();
    $accesR=false;
    if($docDirect->id!='' ){
      $where="idDocumentDirectory=$docDirect->id";
      $lstDocR=$dR->getSqlElementsFromCriteria(null,null,$where);
    }
    if($docDirect->id=='' or empty($lstDocR)){
      $accesR=true;
      $where="idMenu=102";
      $accessRight=new AccessRight();
      $lstDocR=$accessRight->getSqlElementsFromCriteria(null,null,$where);
    }
    
    foreach ($lstDocR as $idR=>$docR){
      if(pq_array_key_exists($docR->idProfile, $columnList)){
        unset($newProfList[$docR->idProfile]);
      }
      $lstDocRight[$docR->idProfile]=$docR;
    }
    $destinationWidth=((RequestHandler::getNumeric('destinationWidth')*0.98)*0.93)-5;
    $widthSelect=intval($destinationWidth/($nbProf+2)-30);
     echo '<tr><td colspan="4">';
     if($docDirect->id!=''){
       echo '<div id="documenDirectory" dojotype="dijit.layout.ContentPane" >';
       $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array("id"=>258));
       $goto=' onClick="loadMenuBarItem(\''.$classDR.'\',\''.htmlEncode(addslashes(i18n($menu->name)),'quotes').'\',\'bar\');showMenuBottomParam(\''.$classDR.'\',\'false\');" ';
       echo '<tr><td colspan="4">';
       echo '   <div class="roundedVisibleButton roundedButton generalColClass" style="width:300px;text-align: left;position: relative; margin-top: 30px;height: 25px;margin-left: 70px" '.$goto.'>';
       echo '     <img src="css/customIcons/new/iconMoveTo.svg" class="imageColorNewGui" style="position:relative;left:5px;top:2px;top:4px;width:16px;height:16px">';
       echo '     <div style="position:relative;top:-16px;left:25px;">'.i18n('menuDocumentRight').'</div>';
       echo '   </div>';
     
     }
     echo '<table style="width:100%;margin-top: 30px;">';
     
     echo '   <tr>';
     echo '    <td>';
     echo '     <div style="width:'.$destinationWidth.'px; overflow-x:auto;  overflow-y:hidden; text-align: -webkit-center;">';
     echo '       <table class="crossTable" >';
                      foreach ($columnList as $col) {
     echo '             <td class="tabLabel" style="width:'.$widthSelect.'px;">' . $col . '</td>';
                      }
     echo '         </tr>';
     echo '         <tr>';
                      foreach ($columnList as $idP=>$namP){
                        if(pq_array_key_exists($idP, $lstDocRight)){
                          $name="documentRight_" .$idP ;
                          echo '<td class="crossTablePivot">';
                          echo '  <select dojoType="dijit.form.FilteringSelect" class="input" '.(($rightUpdate=='NO' and $rightRead=='YES')?"readonly":"");
                          echo      autoOpenFilteringSelect();
                          echo '    style=" width:'.$widthSelect.'px;min-width: 100px;font-size: 80%;" id="' . $name . '" name="' . $name . '" >';
                          htmlDrawOptionForReference('idAccessProfile', (($docDirect->id!='' and !$accesR)?$lstDocRight[$idP]->idAccessMode:$lstDocRight[$idP]->idAccessProfile), null, true);
                          echo '  </select>';
                          echo '</td>';
                        }else if(pq_array_key_exists($idP, $newProfList)){
                         $name="documentRight_" . $idP ;
                         echo '<td class="crossTablePivot">';
                         echo '  <select dojoType="dijit.form.FilteringSelect" class="input" '.(($rightUpdate=='NO' and $rightRead=='YES')?"readonly":"");
                         echo      autoOpenFilteringSelect();
                         echo '    style=" width:'.$widthSelect.'px;min-width: 100px;font-size: 80%;" id="' . $name . '" name="' . $name . '" >';
                         htmlDrawOptionForReference('idAccessProfile',9, null, true);
                         echo '  </select>';
                         echo '</td>';
                       }
                     }
     echo '         </tr>';
     echo '       </table>';
     echo '         <input id="lstDocRight" name="lstDocRight" value="'.implode(',',array_flip($columnList)).'" type="hidden" />';
     echo '     </div>';
     echo '    </td>';
     echo '   </tr>';
     echo '   <tr>';
     echo '   </tr>';
     echo '</table>';
     echo '</div></td></tr>';
     echo '</td></tr>';
  }
  

}
?>