<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2016 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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

$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
$objectId = RequestHandler::getId('objectId');
$objectClass = RequestHandler::getClass('objectClass');
$obj = new $objectClass($objectId,true);
$idProject = $obj->idProject;

?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='userStoryForm' name='userStoryForm' onSubmit="return false;">
       	 <input type="hidden" id="objectId" name="objectId" value="<?php echo $objectId;?>" />
       	 <input type="hidden" id="objectClass" name="objectClass" value="<?php echo $objectClass;?>" />
       	 <input type="hidden" id="idProject" name="idProject" value="<?php echo $idProject;?>" />
         <table>
           <tr>
             <td class="dialogLabel" >
               <label for="userStoryId" style="white-space:nowrap;width:100px;"><?php echo i18n("colIdUserStory");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <table><tr><td>
               <div id="dialogUserStoryList" dojoType="dijit.layout.ContentPane" region="center">
                 <input id="userStoryId" name="userStoryId" type="hidden" value=""/>
               </div>
               </td><td style="vertical-align: top;">
               <div style="width: 100%;">
                 <button id="userStoryDetailButton" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                   <script type="dojo/connect" event="onClick" args="evt">
                    var canCreate=("<?php echo securityGetAccessRightYesNo('menuUserStory','create');?>"=="YES")?1:0;
                    showDetail('userStoryId', canCreate , 'UserStory', true);
                   </script>
                 </button>
               </div>
               </td></tr></table>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogUserStory').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogUserStorySubmit" onclick="protectDblClick(this);saveUserStory();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
