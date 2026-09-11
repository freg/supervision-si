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
//test
/** ============================================================================
 * Action is establised during meeting, to define an action to be followed.
*/
require_once('_securityCheck.php');
class ProspectEvent extends SqlElement {

  public $_sec_description;
  public $id;
  public $refType;
  public $refId;
  public $idUser;
  public $eventDateTime;
  public $name;
  public $idProspectEventType;
  public $idContact;
  public $idle;
  public $description;

  private static $_fieldsAttributes=array(
      "idUser"=>"hidden",
      "refType"=>"hidden",
      "refId"=>"hidden",
      "eventDateTime"=>"required",
      "name"=>"required",
      "idProspectEventType"=>"required",
  );

  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th> 
    <th field="name" width="50%" formatter="translationFormatter">${name}</th>
    <th field="date" formatter="dateFormatter" width="30%">${date}</th> 
    <th field="nameProspectEventType" width="40%">${idProspectEventType}</th>   
    ';

  private static $_colCaptionTransposition = array('idResource'=> 'responsible');

  private static $_databaseColumnName = array();

  /** ==========================================================================
   * Name of a contact, as the lists show it. fullName carries it, name being often
   * empty on a contact, and the Contact class does not declare fullName : the two
   * are read in turn.
   * @param $idContact Int the contact, or nothing
   * @return String the name, or an empty string
   */
  public static function contactName($idContact) {
    $id=intval($idContact);
    if (! $id) return '';
    $name=SqlList::getFieldFromId('Contact', $id, 'fullName');
    if (! $name) $name=SqlList::getNameFromId('Contact', $id);
    return $name;
  }

  /** ==========================================================================
   * Draws the list of actions a record carries, as its section shows it. The three
   * records that carry such a section - client, prospect and contact - read the
   * list through this method, so a column added here appears on all of them.
   * @param $owner SqlElement the record the section belongs to
   * @param $criteria Array what selects the actions of that record
   * @param $withContact Boolean whether the contact column is drawn
   * @param $where String a raw clause, for what an array of criteria cannot say :
   *        a client shows its own actions and those of its contacts, which is an
   *        alternative, where an array only expresses a conjunction.
   * @return void
   */
  public static function drawList($owner, $criteria, $withContact, $where=null) {
    global $print;
    $canUpdate=securityGetAccessRightYesNo('menu'.get_class($owner), 'update', $owner)=="YES";
    if ($owner->idle==1) {
      $canUpdate=false;
    }
    // The contact column takes its width from the two it stands between.
    $widthType=$withContact ? '20' : '25';
    $widthName=$withContact ? '45' : '65';
    echo '<table style="width:100%;">';
    echo '<tr>';
    if (!$print) {
      echo '<td class="linkHeader" style="width:5%">';
      if ($owner->id!=null and !$print and $canUpdate) {
        echo '<a onClick="addProspectEvent();" title="'.i18n('addProspectEvent').'" class="roundedButtonSmall">'.formatSmallButton('Add').'</a>';
      }
      echo '</td>';
    }
    echo '<td class="linkHeader" style="width:'.(($print)?'10':'5').'%">'.i18n('colId').'</td>';
    echo '<td class="linkHeader sortable" style="width:'.$widthType.'%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colType').'</td>';
    if ($withContact) {
      echo '<td class="linkHeader sortable" style="width:20%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colIdContact').'</td>';
    }
    echo '<td class="linkHeader sortable" style="width:'.$widthName.'%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
    echo '</tr>';
    $pe=new ProspectEvent();
    $list=$pe->getSqlElementsFromCriteria($criteria, null, $where, 'eventDateTime DESC');
    foreach ($list as $event) {
      // The row was opened nowhere : the cells stood between two rows and the
      // browser was left to guess where they belonged.
      echo '<tr>';
      if (!$print) {
        echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
        echo '  <a onClick="editProspectEvent('."'".htmlEncode($event->id)."'".');" title="'.i18n('editProspectEvent').'" > '.formatSmallButton('Edit').'</a>';
        echo '  <a onClick="removeProspectEvent('."'".htmlEncode($event->id)."'".');" title="'.i18n('removeProspectEvent').'" > '.formatSmallButton('Remove').'</a>';
        echo '</td>';
      }
      echo '<td class="linkData">#'.$event->id.'</td>';
      echo '<td class="linkData">'.SqlList::getNameFromId('ProspectEventType',$event->idProspectEventType).'</td>';
      if ($withContact) {
        echo '<td class="linkData">'.htmlEncode(self::contactName($event->idContact)).'</td>';
      }
      echo '<td class="linkData">';
      echo '<table style="width:100%; border-collapse:collapse;"><tr>';
      echo '<td style="text-align:left; vertical-align:top;">';
      echo htmlEncode($event->name);
      echo '</td>';
      echo '<td style="text-align:right; vertical-align:center;">';
      echo '<span style="display:inline-block;position: relative; top:-6px;">';
      if ($event->description) {
        echo formatCommentThumb('<b>'.ucfirst(i18n('colDescription')).":</b>\n\n".$event->description, null,true);
      }
      echo '</span>';
      echo '<span style="display:inline-block;margin-left:2px;">';
      echo formatUserThumb($event->idUser, SqlList::getNameFromId('Affectable', $event->idUser), 'Creator');
      echo '</span>';
      echo '<span style="display:inline-block; margin-left:7px;">';
      echo formatDateThumb($event->eventDateTime, null);
      echo '</span>';
      echo '</td></tr></table></td>';
      echo '</tr>';
    }
    echo '</table>';
    echo '<input id="ProspectEventCount" type="hidden" value="'.count($list).'" />';
  }

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

  public function save() {
    $result = parent::save();
    return $result;
  }

  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */

  protected function getStaticLayout() {
    return self::$_layout;
  }

  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return array_merge(parent::getStaticFieldsAttributes(),self::$_fieldsAttributes);
  }

  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }

  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }

  /** ============================================================================
   * Set attribut from parent : merge current attributes with those of Main class
   * @return void
   */
  public function setAttributes() {


  }

}
?>