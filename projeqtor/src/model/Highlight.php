<?php
/*
 *	@author: qCazelles 
 */

require_once('_securityCheck.php');
class Highlight extends SqlElement {
	
	public $id;   
	public $idUser;
	public $scope;
	public $date;
	public $reference;
	public $_noHistory=true;
  	

	/** ==========================================================================
	 * Construct
	 * @return void
	 */
	function __construct($id = NULL, $withoutDependentObjects=false) {
		parent::__construct($id,$withoutDependentObjects);
	}
	
	public function save() {
	  $result = parent::save();
	  return $result;
	}
	
	/** ==========================================================================
	 * Destructor
	 * @return void
	 */
	function __destruct() {
		parent::__destruct();
	}

	
	
}